#!/usr/bin/env python3
"""
Fix RQ enqueue_call compatibility: rq >= 1.0 removed enqueue_call() in
favour of enqueue(). CKAN's ckan/lib/jobs.py still uses enqueue_call()
which silently creates the job hash without pushing it onto the queue
list, causing workers to never pick up jobs.
"""
import sys

path = 'ckan/lib/jobs.py'

with open(path, 'r') as f:
    content = f.read()

old = (
    '    job = get_queue(queue).enqueue_call(\n'
    '        func=fn, args=args, kwargs=kwargs, **rq_kwargs)'
)

new = (
    '    # rq >= 1.0 removed enqueue_call() in favour of enqueue().\n'
    '    q = get_queue(queue)\n'
    '    if hasattr(q, \'enqueue_call\'):\n'
    '        log.info(u\'enqueue: using enqueue_call (rq < 1.0) for queue "%s"\', queue)\n'
    '        job = q.enqueue_call(func=fn, args=args, kwargs=kwargs, **rq_kwargs)\n'
    '    else:\n'
    '        log.info(u\'enqueue: using enqueue (rq >= 1.0) for queue "%s"\', queue)\n'
    '        job = q.enqueue(fn, args=args, kwargs=kwargs, **rq_kwargs)\n'
    '    log.info(u\'enqueue: job %s created, origin queue key: %s\', job.id, job.origin)'
)

if old not in content:
    print(f'ERROR: expected pattern not found in {path}', file=sys.stderr)
    sys.exit(1)

with open(path, 'w') as f:
    f.write(content.replace(old, new, 1))

print(f'Patched {path} successfully')
