"""XGBoost introspector."""

from __future__ import annotations

from typing import Any

from model_ledger.introspect.models import FeatureInfo, IntrospectionResult


class XGBoostIntrospector:
    name = "xgboost"

    def can_handle(self, obj: Any) -> bool:
        try:
            import xgboost as xgb

            return isinstance(obj, (xgb.Booster, xgb.XGBModel))
        except ImportError:
            return False

    def introspect(self, obj: Any) -> IntrospectionResult:
        import xgboost as xgb

        if isinstance(obj, xgb.XGBModel):
            params = obj.get_params()
            features = []
            if hasattr(obj, "feature_names_in_"):
                features = [FeatureInfo(name=str(n)) for n in obj.feature_names_in_]
            metrics = {}
            if hasattr(obj, "best_score") and obj.best_score is not None:
                metrics["best_score"] = obj.best_score
            return IntrospectionResult(
                introspector=self.name,
                framework="xgboost",
                algorithm=type(obj).__name__,
                hyperparameters=params,
                features=features,
                metrics=metrics,
            )

        # Raw Booster
        features = []
        if obj.feature_names:
            features = [FeatureInfo(name=n) for n in obj.feature_names]
        config = obj.save_config()
        return IntrospectionResult(
            introspector=self.name,
            framework="xgboost",
            algorithm="Booster",
            features=features,
            metadata={"config": config},
        )
