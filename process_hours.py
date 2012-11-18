#!/usr/bin/env python

# TIFMASTER DATABASE UPDATER
#
# This accepts a series of text files containing daily hours records,
# and adds them to the TIFmaster database.  Vacation credit, median
# adjustments, chart rotations, etc. are also performed as needed.
#
# Running the program without any input files will just print out some
# basic info on the current database state, primarily to determine what
# the last-processed day record was.
#
# Since the process of median advancement and chart rotation is a somewhat
# irreversible procedure, it is important to process days in order rather
# than try to insert hours later.

import tif
import sys
import re
from datetime import timedelta

debug = True

record_re = re.compile('([A-Z]+)=?([.0-9]*)/?([.0-9]*)([a-z]*)')

def read_hours_file(fn,days=dict()):
    with open(fn,'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('$'): continue
            if line.startswith('#'): continue
            if len(line) < 1: continue
            if debug: print line
            try:
                date, rest = line.split(None,1)
            except ValueError:
                date = line
                rest = ""
            date = tif.from_iso(date)
            if date <= tif.max_date():
                raise Exception("Date %s falls into previous record range." % date)
            for record in rest.split():
                sign = 1.0
                if '-' in record:
                    sign = -1.0
                    record = record.replace('-','')
                key, hour, factor, flags = record_re.match(record).groups()
                if ""==hour:
                    hour=1
                if ""==factor:
                    factor=1
                minutes = int(60.0*sign*float(hour)/float(factor))
                try:
                    key=tif.from_initials(key)                    
                except:
                    raise Exception("Keyholder %s not found." % key)
                if key.active_on(date):
                    record = dict(key=key,
                                  minutes=timedelta(minutes=minutes),
                                  flags=flags)
                    if date in days:
                        days[date].append(record)
                    else:
                        days[date]=[record]
                else:
                    raise Exception("%s contains invalid keyholder %s." % (fn,key))
    return days

def read_hours_files(fns):
    acc = dict()
    for fn in fns:
        acc = read_hours_file(fn,acc)
    return acc

def update_hours(days):
    for date in days.iterkeys():
        # New Keyholders get boosted to the median
        for key in tif.Keyholder.keyholders.itervalues(): 
            if key.start_date == date:
                key.credits = tif.Keyholder.keyholders['MED'].credits
        # And then we add the work on that day
        for record in days[date]:
            record['key'].add_work(tif.Credit(date,
                                              record['minutes'],
                                              record['flags']))
        old = tif.last_median() # in minutes
        new = tif.compute_median()
        the_median = tif.from_initials(tif.MEDIAN)
        while ((new - old) >= tif.MEDIAN_INCREMENT):
            the_median.add_work(tif.Credit(date,
                                           tif.MEDIAN_INCREMENT))
            old = tif.last_median()
            for key in tif.Keyholder.keyholders.itervalues():
                if key.active_on(date) and key.gets_vacation(date):
                    key.add_work(tif.Credit(date,
                                            tif.MEDIAN_INCREMENT,
                                            "a"))
                    print "%s gets %d minutes of vacation credit on %r." % (key.initials, tif.MEDIAN_INCREMENT.seconds/60, date)
        old = tif.last_median()
        while (old >= tif.ROTATION_MAX):
            the_median.add_lameness(tif.Credit(date,
                                               tif.ROTATION_MAX - tif.ROTATION_MIN))
            minmed = tif.min_median_date()
            for key in tif.active_keys(date):
                key.add_lameness(tif.Credit(date,
                                            tif.ROTATION_MAX - tif.ROTATION_MIN))
                key.expire_lameness(minmed)
            old = tif.last_median()
            print "Chart rotates, median moves back to %s on %s." % (tif.to_hours(tif.last_median()), date)

if __name__=='__main__':
    tif.load()
    print "Median range starts at %s." % tif.min_median_date()
    print "Last date of record is %s." % tif.max_date()
    days = read_hours_files(sys.argv[1:])
    update_hours(days)
    tif.write_credits()
    tif.write_debits()
