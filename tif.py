#!/usr/bin/env python

from datetime import timedelta, date
import re, math

## Constants
KEYHOLDERS_FN    = "TIF_keyholders.txt"
VACATIONS_FN     = "TIF_vacations.txt"
CREDITS_FN       = "TIF_credits.txt"
DEBITS_FN        = "TIF_debits.txt"
MEDIAN           = "MED"
MEDIAN_INCREMENT = timedelta(hours=1)
ROTATION_MIN     = timedelta(hours=39)
ROTATION_MAX     = timedelta(hours=40)
HARD_LIMIT_TOP   = timedelta(hours=104)
FULL_SURPLUS     = timedelta(hours=39)
SURPLUS_LIMIT    = timedelta(hours=65)

verbose = False

zero_t = timedelta(minutes=0)

class Keyholder:
    keyholders=dict()
    def __init__(self,initials,start_date,end_date):
        self.initials = initials
        self.start_date = start_date
        self.end_date = end_date
        self.vacations = []
        self.credits = []
        self.debits = []
        self.credit_total = zero_t
        self.debit_total = zero_t
        Keyholder.keyholders[initials] = self 
    def gets_vacation(self,d):
        """Checks whether this keyholder should get vacation credit
        for a Median advance on the date $d$.  Takes the two-week
        delay into account."""
        for (start,end) in self.vacations:
            if (start <= d.isoformat()) and (d.isoformat() <= end):
                return True
        return False
    def active_on(self,d):
        return (self.start_date <= d) and (d <= self.end_date)
    def active(self):
        return self.active_on(date.today())
    def current_balance(self):
        return self.credit_total + self.debit_total
    def add_work(self, credit):
        """Register work, adjusting debits and credits as appropriate"""
        if credit.time < zero_t:            
            # Keyholder received a debit
            self.debits.append(credit)
            self.debit_total += credit.time
            return
        elif self.debit_total + credit.time < zero_t: 
            # A credit purely making up for debit
            credit.adjust_for_behindness(self.debit_total)
            self.debits.append(credit)
            self.debit_total += credit.time
            return
        if self.debit_total < zero_t:
            self.debits.append(Credit(credit.date,
                                  -1*self.debit_total,
                                  credit.flags))
            credit.time += self.debit_total
            self.debit_total = zero_t
            if credit.time <= zero_t: return
        # adjust minutes if far ahead of the median
        median = last_median()
        if self.credit_total-median > FULL_SURPLUS: 
            fraction = 1.0 - (float(minutes(self.credit_total-median-FULL_SURPLUS)) /
                              float(minutes(SURPLUS_LIMIT-FULL_SURPLUS)))
            if fraction > 0:
                credit.set_minutes(int(credit.minutes()*fraction))
        if self.credit_total+credit.time > HARD_LIMIT_TOP:
            credit.time = HARD_LIMIT_TOP-self.credit_total
        if credit.minutes() <= 0: return
        self.credits.append(credit)
        self.credit_total += credit.time
    def add_lameness(self, debit):
        """Register a missed session, removing existing credits as
        appropriate, then adding debits as the median advances."""
        while debit.minutes() > 0:
            if len(self.credits) > 0:
                record = self.credits[0]
                if record.time > debit.time:
                    # subtract some time from a credit in place
                    record.time -= debit.time
                    self.credit_total -= debit.time
                    debit.set_minutes(0)
                else:
                    # consume a credit entirely
                    debit.time -= record.time
                    self.credit_total -= record.time
                    self.credits = self.credits[1:]
            else:
                # no credits, add a Black Mark
                self.debits.append(Credit(debit.date,
                                      -debit.time,
                                      'a')) # a)uto
                self.debit_total -= debit.time
                debit.time -=debit.time
    def expire_lameness(self,d):
        """Remove any cancelling debit-credit pairs before date $d$"""
        total=0
        newdebits=[]
        olddebits=[]
        for record in self.debits:
            if record.minutes() > 0:
                newdebits.append(record)
                total += record.minutes()
            elif record.date >= d:
                newdebits.append(record)
            else:
                olddebits.append(record)
        anti_minutes = total
        self.debits = []
        for record in olddebits:
            if total > 0:
                if -(record.minutes()) <= total:
                    total += record.minutes()
                else:
                    record.add_minutes(total)
                    total = 0
                    self.debits.append(record)
            else:
                self.debits.append(record)
        for record in newdebits:
            if record.minutes() > 0 and total < anti_minutes: 
                if record.minutes() <= (anti_minutes - total):
                    total += record.minutes()
                else:
                    record.add_minutes(total-anti_minutes)
                    self.debits.append(record)
                    total = anti_minutes
            else: 
                self.debits.append(record)


def from_initials(i):
    return Keyholder.keyholders[i]

class Credit:
    def __init__(self,date, time, flags=""):
        self.date = date
        self.time = time
        self.flags = flags
    def minutes(self):        
        return minutes(self.time)
    def set_minutes(self,m):
        self.time = timedelta(minutes=m)
    def add_minutes(self,m):
        self.time += timedelta(minutes=m)
    def adjust_for_behindness(self,debt):
        median_time = (24*60*60 * ROTATION_MAX.days + ROTATION_MAX.seconds)
        debt_time = abs(24*60*60 * debt.days + debt.seconds)
        factor = (median_time + debt_time)//median_time
        self.time *= factor
        


def minutes(t):
    return t.seconds//60 + t.days*60*24

def to_hours(t):
    return t.days*24+t.seconds//(60*60)

def hours_minutes(t):
    s = ""
    m = minutes(t)
    if m < 0:
        s += '-'
        m *= -1
    hours = math.trunc(m/60.0)
    mins = m % 60
    return "%s%d:%02d" % (s,hours,mins)

class FormatError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def load_keyholders(fn=KEYHOLDERS_FN):
    keys=[]
    with open(fn,'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'): continue
            if len(line.split()) == 3:
                key, start, end = line.split()
                start_yr, start_mn, start_dy = start.split('-')
                end_yr, end_mn, end_dy = end.split('-')
                if verbose:
                    print ("Creating date %s-%s-%s" % 
                           (start_yr,start_mn,start_dy))
                start = date(int(start_yr),int(start_mn),int(start_dy))
                end = date(int(end_yr),int(end_mn),int(end_dy))
            elif len(line.split()) == 2:
                key, start = line.split()
                start_yr, start_mn, start_dy = start.split('-')
                start = date(int(start_yr),int(start_mn),int(start_dy))
                end = date.max
            elif len(line.split()) == 1:
                key = line.split()[0]
                start = date.min
                end = date.max
            else:
                raise FormatError()
            if verbose:
                print "Read keyholder %s from %s to %s" % (key,
                                                           start.isoformat(),
                                                           end.isoformat())
            keys.append(Keyholder(key,start,end))
    keys.append(Keyholder(MEDIAN,date.min,date.max))
    return keys

def load_vacations(fn=VACATIONS_FN):
    with open(fn,'r') as f:
        for line in f:
            line=line.strip();
            if line.startswith('#'): continue
            key,start,end = line.split()
            try:
                Keyholder.keyholders[key].vacations.append((start,end))
            except KeyError:
                print ("Read vacation for non-keyholder %s." % key)
                raise

def from_iso(s):
    """Takes YYYY-MM-DD to a date object"""
    (yr,mo,dy)=s.split('-')
    return date(int(yr),int(mo),int(dy))

credit_re = re.compile('(.*)=(\d+)([a-z]*)')

def load_credits(fn=CREDITS_FN):
    with open(fn,'r') as f:
        for line in f:
            line=line.strip()
            if line=="": continue
            if line.startswith('#'): continue
            records = line.split()
            key = records[0]
            for record in records[1:]:
                date, minutes, flags = credit_re.match(record).groups()
                try:
                    #if key==MEDIAN: continue
                    Keyholder.keyholders[key].credits.append(
                        Credit(from_iso(date),
                               timedelta(minutes=int(minutes)),
                               flags))
                except KeyError:
                    print ("Read credit for non-keyholder %s." % key)
                    exit(1)
        for key in Keyholder.keyholders.values():
            key.credit_total=zero_t
            for record in key.credits:
                key.credit_total += record.time

debit_re = re.compile('(.*)=(-?\d+)([a-z]*)')

def load_debits(fn=DEBITS_FN):
    with open(fn,'r') as f:
        for line in f:
            line=line.strip();
            if line=="": continue
            if line.startswith('#'): continue
            records = line.split()
            key = records[0]
            for record in records[1:]:
                date, minutes, flags = debit_re.match(record).groups()
                try:
                    Keyholder.keyholders[key].debits.append(
                        Credit(from_iso(date),
                               timedelta(minutes=int(minutes)),
                               flags))
                except KeyError:
                    print ("Read debit for non-keyholder %s." % key)
                    exit(1)
        for key in Keyholder.keyholders.values():
            key.debit_total=zero_t
            for debit in key.debits:
                key.debit_total += debit.time
            if (key.debit_total > zero_t):
                print "Warning: keyholder %s has positive debits." \
                    % key.initials

def write_activity(filename,f):
    with open(filename,'w') as fl:
        keys = Keyholder.keyholders.items()
        keys.sort()
        for (name,key) in keys:
            fl.write(key.initials)
            if verbose: print "Writing keyholder %s." % key.initials
            for record in f(key):
                fl.write(' %s=%s%s' % (record.date,
                                       record.minutes(),
                                       record.flags))
            fl.write("\n\n")
                      
def write_credits(fn=CREDITS_FN):
    write_activity(fn, lambda x: x.credits)

def write_debits(fn=DEBITS_FN):
    write_activity(fn, lambda x: x.debits)

def active_keys(d):
    return [x for x in Keyholder.keyholders.values() if x.active_on(d)]

def min_median_date():
    m = date.max
    for record in Keyholder.keyholders[MEDIAN].credits:
        if record.date < m:
            m = record.date
    return m

def max_median_date():
    m = date.min
    for record in Keyholder.keyholders[MEDIAN].credits:
        if record.date > m:
            m = record.date
    return m

def max_date():
    m = date.min
    for key in Keyholder.keyholders.values():
        for record in (key.credits + key.debits):
            if record.date > m: 
                m = record.date
    return m

def last_median():
    """Minutes total for the median last record (i.e., not freshly computed)"""
    return Keyholder.keyholders[MEDIAN].credit_total

def compute_median():
    """Computes the median for the list of current keyholders.  To make
the median advance a little more gradually, it's given as the mean of
the keyholders at the 1/3, 1/2, and 2/3 level."""
    totals = [] #totals = [x.credit_total for x in Keyholder.keyholders.itervalues()]
    for x, y in Keyholder.keyholders.items():
        if y.active():
            totals.append(y.credit_total)
    totals.sort()
    l = len(totals)
    return (totals[l//3] + totals[l//2] + totals[2*l//3])//3

def load():
    load_keyholders()
    load_vacations()
    load_credits()
    load_debits()

if __name__=='__main__':
    load()
    write_credits('/tmp/new-credits')
    write_debits('/tmp/new-debits')
