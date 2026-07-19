"""sklearn introspector — extracts metadata from scikit-learn estimators."""

from __future__ import annotations

from typing import Any

from model_ledger.introspect.models import (
    ComponentInfo,
    FeatureInfo,
    IntrospectionResult,
)


class SklearnIntrospector:
    name = "sklearn"

    # Frameworks whose sklearn-API wrappers subclass BaseEstimator but have
    # dedicated introspectors. The generic sklearn introspector must defer to
    # those regardless of registry iteration order.
    _WRAPPER_MODULES = frozenset({"xgboost", "lightgbm"})

    def can_handle(self, obj: Any) -> bool:
        try:
            from sklearn.base import BaseEstimator
        except ImportError:
            return False
        if not isinstance(obj, BaseEstimator):
            return False
        root_module = (type(obj).__module__ or "").split(".", 1)[0]
        return root_module not in self._WRAPPER_MODULES

    def introspect(self, obj: Any) -> IntrospectionResult:
        from sklearn.pipeline import Pipeline

        if isinstance(obj, Pipeline):
            return self._introspect_pipeline(obj)
        return self._introspect_estimator(obj)

    def _introspect_estimator(self, obj: Any) -> IntrospectionResult:
        features = []
        if hasattr(obj, "feature_names_in_"):
            features = [FeatureInfo(name=str(n)) for n in obj.feature_names_in_]

        return IntrospectionResult(
            introspector=self.name,
            framework="scikit-learn",
            algorithm=type(obj).__name__,
            hyperparameters=obj.get_params(deep=False),
            features=features,
        )

    def _introspect_pipeline(self, pipe: Any) -> IntrospectionResult:
        components = []
        final_estimator = None

        for i, (_step_name, step_obj) in enumerate(pipe.steps):
            cls_name = type(step_obj).__name__
            is_final = i == len(pipe.steps) - 1
            node_type = "algorithm" if is_final else "preprocessor"
            components.append(
                ComponentInfo(
                    path=f"Processing/{cls_name}",
                    node_type=node_type,
                    metadata=step_obj.get_params(deep=False),
                )
            )
            if is_final:
                final_estimator = step_obj

        features = []
        if hasattr(pipe, "feature_names_in_"):
            features = [FeatureInfo(name=str(n)) for n in pipe.feature_names_in_]

        algorithm = type(final_estimator).__name__ if final_estimator else "Pipeline"

        return IntrospectionResult(
            introspector=self.name,
            framework="scikit-learn",
            algorithm=algorithm,
            hyperparameters=final_estimator.get_params(deep=False) if final_estimator else {},
            features=features,
            components=components,
        )
