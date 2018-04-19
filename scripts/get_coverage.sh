#!/bin/bash

python_script="
import sys
covered,uncovered = [int(s) for s in sys.stdin.readline().split(chr(32))]
if covered+uncovered == 0:
    print('No lines given!')
else:
    n = round(100*covered/(covered+uncovered), 3)
    print('{n}%'.format(n=n).ljust(7), '- {x} covered,'.format(x=covered).ljust(14), '{y} uncovered'.format(y=uncovered))
"

cd /tmp
trial --coverage theseus

echo "Getting coverage statistics..."
echo
cd _trial_temp/coverage

total_covered=0
total_uncovered=0

for fname in $(ls | grep theseus | grep -v "test\|__init__"); do
    uncovered=$(cat $fname | grep '^>>>>>>' | wc -l)
    covered=$(cat $fname | grep -v '^>>>>>>' | wc -l)
    #echo -n "$fname - "
    python3 -c "print('$fname'.ljust(28), end='')"
    echo $covered $uncovered | python3 -c "$python_script"
    total_covered=$(( total_covered + covered ))
    total_uncovered=$(( total_uncovered + uncovered ))
done

echo
echo -n "Total - "
echo $total_covered $total_uncovered | python3 -c "$python_script"
echo

