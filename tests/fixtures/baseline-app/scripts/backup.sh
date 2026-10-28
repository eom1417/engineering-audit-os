#!/bin/sh
# The nightly backup of the orders.
pg_dump "$DATABASE_URL" -t orders -f backup.sql
