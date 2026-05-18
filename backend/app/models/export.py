from __future__ import annotations

from typing import Any, Mapping

from .base import SimLayModel
from .valuation import should_export_price


class WixExportPolicy(SimLayModel):
    blank_unknown_confidence_price: bool = True
    require_passed_valuation_gates: bool = True
    require_export_value: bool = True

    def price_value_or_blank(self, item: Mapping[str, Any], value: Any) -> Any:
        if self.blank_unknown_confidence_price or self.require_passed_valuation_gates or self.require_export_value:
            if not should_export_price(item):
                return ""
        return value if value is not None else ""


DEFAULT_WIX_EXPORT_POLICY = WixExportPolicy()
