"""A number box that shows sizes the way people write them: 24.00 in,
0.125 in, 6.875 in. It keeps full precision while showing at least two
decimals, so a 0.125 in bleed is never rounded to 0.13."""

from PyQt5.QtWidgets import QDoubleSpinBox

from . import units


class NumberBox(QDoubleSpinBox):
    def textFromValue(self, value):
        return units.tidy(value, self.decimals())
