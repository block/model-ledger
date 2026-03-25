"""LightGBM introspector."""

from __future__ import annotations

from typing import Any

from model_ledger.introspect.models import FeatureInfo, IntrospectionResult


class LightGBMIntrospector:
    name = "lightgbm"

    def can_handle(self, obj: Any) -> bool:
        try:
            import lightgbm as lgb

            return isinstance(obj, (lgb.Booster, lgb.LGBMModel))
        except ImportError:
            return False

    def introspect(self, obj: Any) -> IntrospectionResult:
        import lightgbm as lgb

        if isinstance(obj, lgb.LGBMModel):
            params = obj.get_params()
            features = []
            if hasattr(obj, "feature_name_"):
                features = [FeatureInfo(name=str(n)) for n in obj.feature_name_]
            metrics = {}
            if hasattr(obj, "best_score_") and obj.best_score_:
                metrics.update(
                    {
                        f"{ds}_{metric}": val
                        for ds, metrics_dict in obj.best_score_.items()
                        for metric, val in metrics_dict.items()
                    }
                )
            return IntrospectionResult(
                introspector=self.name,
                framework="lightgbm",
                algorithm=type(obj).__name__,
                hyperparameters=params,
                features=features,
                metrics=metrics,
            )

        # Raw Booster
        features = []
        if obj.feature_name():
            features = [FeatureInfo(name=n) for n in obj.feature_name()]
        return IntrospectionResult(
            introspector=self.name,
            framework="lightgbm",
            algorithm="Booster",
            features=features,
        )
