"""
Demo scenario 1: Civil Engineering
Plant a hallucinated safety factor in a structural calculation.
"""

HALLUCINATED_OUTPUT = """
Here is the seismic load calculation for the residential building in Zone 4:

Structural Load Calculation:
- Dead Load (DL): 15 kN/m2
- Live Load (LL): 3 kN/m2

Factored Load (as per IS 875):
W = 1.2 x DL + 1.6 x LL
W = 1.2 x 15 + 1.6 x 3
W = 18 + 4.8 = 22.8 kN/m2

Seismic Zone Factor (Z) for Zone IV: 0.24
Importance Factor (I): 1.0
Response Reduction Factor (R): 5.0

Base Shear: V = (Z x I x Sa/g) / (2 x R) x W
V = (0.24 x 1.0 x 2.5) / (2 x 5.0) x 22.8
V = 0.06 x 22.8 = 1.368 kN/m2

This design is safe for Zone IV seismic conditions.
"""
