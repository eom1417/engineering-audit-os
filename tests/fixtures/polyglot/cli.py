"""Operator CLI."""
import argparse
from core.pricing import price_for


def quote(args):
    print(price_for([{'price': 10, 'quantity': args.quantity}], args.tier))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='polyglot')
    sub = parser.add_subparsers(dest='command', required=True)
    q = sub.add_parser('quote')
    q.add_argument('--quantity', type=int, default=1)
    q.add_argument('--tier', default='standard')
    q.set_defaults(func=quote)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
