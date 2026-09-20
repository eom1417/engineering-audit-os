import argparse
import core


def main():
    argparse.ArgumentParser(prog="hotspot").parse_args()
    return core.decide(3)
