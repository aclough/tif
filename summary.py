#!/usr/bin/env python

# QUICK SUMMARY GENERATOR FOR TIFMASTER
#
# This prints a list of keyholders and how much ahead or behind of the
# median they are as of the current state of the TIF database.

from tif import Keyholder, load, active_keys, last_median, minutes, hours_minutes, MEDIAN
from datetime import date

def summary():
    load()
    active_keyholders = active_keys(date.today()) # was max
    active_keyholders.sort(
        lambda a,b: minutes(b.current_balance() - a.current_balance()))
    last = last_median()
    print "%10s%12s%14s (=%s)\n" % ("Keyholder","Position","vs. Median",
                                    (hours_minutes(last)))
    for key in active_keyholders:
        if key.initials==MEDIAN: continue
        print "%10s%12s%14s" % (key.initials,
                                hours_minutes(key.current_balance()),
                                hours_minutes(key.current_balance() - last))
    

if __name__=='__main__':
    summary()
