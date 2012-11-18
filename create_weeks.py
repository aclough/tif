#!/usr/bin/env python

# WEEKLY SCHEDULE CREATOR FOR TIFMASTER
#
# Accepts a template schedule for the first week of term, and creates
# weekly schedules up to a given end date, advancing the days appropriately
# but leaving the hours assignments unchanged.

# FIXME This is terribly non-idiomatic.  Separate dates and hours
# lists are silly; we can just pass a value of type [(date,hours)]
# around, extend it to enddate, then write that.

from tif import from_iso
from datetime import date,timedelta
import sys

def read_proto(filename):
    dates=[]
    hours=[]
    with open(filename,'r') as f:
        for line in f:
            line=line.strip()
            if line.startswith('#'): continue
            if line=='': continue
            date,all_hours = line.split(None, 1)
            dates.append(from_iso(date))
            hours.append(all_hours)
    return (dates,hours)

def write_files(dates,hours,enddate):
    while dates[0] <= enddate:
        filename = 'week_of_%s.txt' % dates[0].isoformat()
        with open(filename,'w') as f:
            print filename
            for i in range(0,7):
                f.write("%s %s\n" % (dates[i], hours[i]))
        dates = next_week(dates)

def next_week(dates):
    return [d + timedelta(days=7) for d in dates]


if __name__=='__main__':
    if len(sys.argv) != 3:
        print "%s [first week schedule.txt] [end date]" % sys.argv[0]
        print "  Outputs files with the names 'week_of_YYYY-MM-DD.txt'."
    else:
        our_name, proto_fn, enddate = sys.argv
        dates,hours = read_proto(proto_fn)
        if len(dates) != 7:
            print "This is not a weekly file, aborting"
            exit(-1)
        write_files(dates,hours,from_iso(enddate))

    
