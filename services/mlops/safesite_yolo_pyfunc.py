import json

import mlflow
from mlflow.pyfunc import PythonModel


class SafeSiteYoloModel(PythonModel):
    def load_context(self, context) -> None:
        from ultralytics import YOLO

        self.model = YOLO(context.artifacts["weights"])

    def predict(
        self,
        context,
        model_input: list[dict[str, str]],
        params=None,
    ):
        prediction_params = params or {}
        confidence = float(prediction_params.get("confidence", 0.25))
        image_size = int(prediction_params.get("image_size", 320))
        device = str(prediction_params.get("device", "cpu"))
        image_paths = [record["image_path"] for record in model_input]
        results = self.model.predict(
            source=image_paths,
            conf=confidence,
            imgsz=image_size,
            device=device,
            verbose=False,
        )

        predictions = []
        for image_path, result in zip(image_paths, results, strict=True):
            detections = []
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().tolist()
                confidences = result.boxes.conf.cpu().tolist()
                class_ids = result.boxes.cls.cpu().tolist()
                for box, score, class_id in zip(
                    boxes, confidences, class_ids, strict=True
                ):
                    integer_class_id = int(class_id)
                    detections.append(
                        {
                            "class_id": integer_class_id,
                            "class_name": result.names[integer_class_id],
                            "confidence": round(float(score), 6),
                            "box_xyxy": [round(float(value), 2) for value in box],
                        }
                    )
            predictions.append(
                {
                    "image_path": image_path,
                    "detection_count": len(detections),
                    "detections_json": json.dumps(detections, separators=(",", ":")),
                }
            )
        return predictions


mlflow.models.set_model(SafeSiteYoloModel())
