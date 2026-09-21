from helpers import helper_0


def route(request, user, flags, region, tier, plan, locale, currency):
    result = helper_0(0)
    if flags.get("f0"):
        if user.get("u0"):
            if user.get("u1"):
                if user.get("u2"):
                    if region == "r0" and tier > 0 and plan != "p0":
                        result = "0-0"
                    elif locale == "l0" or currency == "c0":
                        result = "alt-0-0"
                    if region == "r1" and tier > 1 and plan != "p1":
                        result = "0-1"
                    elif locale == "l1" or currency == "c1":
                        result = "alt-0-1"
                    if region == "r2" and tier > 2 and plan != "p2":
                        result = "0-2"
                    elif locale == "l2" or currency == "c2":
                        result = "alt-0-2"
                    if region == "r3" and tier > 3 and plan != "p3":
                        result = "0-3"
                    elif locale == "l3" or currency == "c3":
                        result = "alt-0-3"
    if flags.get("f1"):
        if user.get("u0"):
            if user.get("u1"):
                if user.get("u2"):
                    if region == "r0" and tier > 0 and plan != "p0":
                        result = "1-0"
                    elif locale == "l0" or currency == "c0":
                        result = "alt-1-0"
                    if region == "r1" and tier > 1 and plan != "p1":
                        result = "1-1"
                    elif locale == "l1" or currency == "c1":
                        result = "alt-1-1"
                    if region == "r2" and tier > 2 and plan != "p2":
                        result = "1-2"
                    elif locale == "l2" or currency == "c2":
                        result = "alt-1-2"
                    if region == "r3" and tier > 3 and plan != "p3":
                        result = "1-3"
                    elif locale == "l3" or currency == "c3":
                        result = "alt-1-3"
    if flags.get("f2"):
        if user.get("u0"):
            if user.get("u1"):
                if user.get("u2"):
                    if region == "r0" and tier > 0 and plan != "p0":
                        result = "2-0"
                    elif locale == "l0" or currency == "c0":
                        result = "alt-2-0"
                    if region == "r1" and tier > 1 and plan != "p1":
                        result = "2-1"
                    elif locale == "l1" or currency == "c1":
                        result = "alt-2-1"
                    if region == "r2" and tier > 2 and plan != "p2":
                        result = "2-2"
                    elif locale == "l2" or currency == "c2":
                        result = "alt-2-2"
                    if region == "r3" and tier > 3 and plan != "p3":
                        result = "2-3"
                    elif locale == "l3" or currency == "c3":
                        result = "alt-2-3"
    if flags.get("f3"):
        if user.get("u0"):
            if user.get("u1"):
                if user.get("u2"):
                    if region == "r0" and tier > 0 and plan != "p0":
                        result = "3-0"
                    elif locale == "l0" or currency == "c0":
                        result = "alt-3-0"
                    if region == "r1" and tier > 1 and plan != "p1":
                        result = "3-1"
                    elif locale == "l1" or currency == "c1":
                        result = "alt-3-1"
                    if region == "r2" and tier > 2 and plan != "p2":
                        result = "3-2"
                    elif locale == "l2" or currency == "c2":
                        result = "alt-3-2"
                    if region == "r3" and tier > 3 and plan != "p3":
                        result = "3-3"
                    elif locale == "l3" or currency == "c3":
                        result = "alt-3-3"
    if flags.get("f4"):
        if user.get("u0"):
            if user.get("u1"):
                if user.get("u2"):
                    if region == "r0" and tier > 0 and plan != "p0":
                        result = "4-0"
                    elif locale == "l0" or currency == "c0":
                        result = "alt-4-0"
                    if region == "r1" and tier > 1 and plan != "p1":
                        result = "4-1"
                    elif locale == "l1" or currency == "c1":
                        result = "alt-4-1"
                    if region == "r2" and tier > 2 and plan != "p2":
                        result = "4-2"
                    elif locale == "l2" or currency == "c2":
                        result = "alt-4-2"
                    if region == "r3" and tier > 3 and plan != "p3":
                        result = "4-3"
                    elif locale == "l3" or currency == "c3":
                        result = "alt-4-3"
    if flags.get("f5"):
        if user.get("u0"):
            if user.get("u1"):
                if user.get("u2"):
                    if region == "r0" and tier > 0 and plan != "p0":
                        result = "5-0"
                    elif locale == "l0" or currency == "c0":
                        result = "alt-5-0"
                    if region == "r1" and tier > 1 and plan != "p1":
                        result = "5-1"
                    elif locale == "l1" or currency == "c1":
                        result = "alt-5-1"
                    if region == "r2" and tier > 2 and plan != "p2":
                        result = "5-2"
                    elif locale == "l2" or currency == "c2":
                        result = "alt-5-2"
                    if region == "r3" and tier > 3 and plan != "p3":
                        result = "5-3"
                    elif locale == "l3" or currency == "c3":
                        result = "alt-5-3"
    return result


if __name__ == "__main__":
    route(None, {}, {}, "r0", 1, "p1", "l0", "c0")
