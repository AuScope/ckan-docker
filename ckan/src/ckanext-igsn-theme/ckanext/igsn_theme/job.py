import time

def simple_job():
    """
    A simple job that just sleeps for a few seconds and then returns a message.
    """
    time.sleep(5)
    print("Job completed successfully.", flush=True)
