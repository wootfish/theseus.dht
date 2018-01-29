#!/bin/bash

killall -q twistd

mkdir -p /tmp/instances
rm -rf /tmp/instances/*
touch /tmp/instances/ports

for i in {0..9}; do
    echo $i
    twistd -y theseus_test_instance.tac --logfile=/tmp/instances/$i.log --pidfile=/tmp/instances/$i.pid
    sleep 0.1
    cat /tmp/instances/*.log | grep ' Now listening on port ' | cut -d' ' -f7,11- > /tmp/instances/ports
done


watch -n 2 'wc -l /tmp/instances/*.log; echo; echo; cat /tmp/instances/*.log | egrep "(Error|error|warn)"'

for fname in /tmp/instances/*.pid; do
    kill $(cat $fname)
done
