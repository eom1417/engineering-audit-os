from ..d.calc import shared_calc as d_calc

def shared_calc(x, y, z):
    if x > 0:
        return d_calc(x, y, z)
    return d_calc(x, y, z)
