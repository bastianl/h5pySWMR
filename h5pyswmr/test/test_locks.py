# -*- coding: utf-8 -*-

from __future__ import print_function

import unittest
import sys
import os
import multiprocessing
import threading
import time
import random
import signal
import uuid


if __name__ == '__main__':
    # add ../.. directory to python path such that we can import the main
    # module
    HERE = os.path.dirname(os.path.realpath(__file__))
    PROJ_PATH = os.path.abspath(os.path.join(HERE, '../..'))
    sys.path.insert(0, PROJ_PATH)

from h5pyswmr.locking import reader, writer, redis_conn


class DummyResource(object):
    """
    Simulates reading and writing to a shared resource.
    """

    def __init__(self, name):
        self.file = name

    @reader
    def read(self, worker_no, suicide=False):
        """
        simulate reading

        Args:
            worker_no: worker number (for debugging)
            suicide: if True, then the current process will commit suicide
                while reading. This is useful for testing if the process
                does clean up its locks.
        """
        pid = os.getpid()
        print(u"❤ {0}worker {1} (PID {2}) reading!"
              .format('suicidal ' if suicide else '', worker_no, pid))
        if suicide:
            print(u"✟ Worker {0} (PID {1}) committing suicide..."
                  .format(worker_no, pid))
            os.kill(pid, signal.SIGTERM)
            print("##### I'm dead, this should not show up! #####")
        else:
            time.sleep(random.random())

    @writer
    def write(self, worker_no):
        """
        simulate writing
        """
        print(u"⚡ worker {0} writing!".format(worker_no))
        time.sleep(random.random())


class TestLocks(unittest.TestCase):
    """
    Unit test for locking module
    """

    def test_locks(self):
        """
        Test parallel read/write access
        """
        # test with threads and processes
        # print("\n##### Running tests with threads... #####")
        # TODO Library does not yet work in multithreaded environment
        # self.run_locks_test(threading.Thread)
        print("\n ##### Running tests with processes... #####")
        self.run_locks_test(multiprocessing.Process)

    def run_locks_test(self, threadclass):
        """
        Run the actual test, either with threads or processes.

        Args:
            threadclass: class, either threading.Thread or
                multiprocessing.Process
        """
        res_name = 'testresource87234ncsdf'
        resource = DummyResource(res_name)

        def worker_read(i, resource):
            """ reading worker """
            time.sleep(random.random() * 2)
            print(u"Worker {0} attempts to read...".format(i))
            if i % 13 == 1:
                resource.read(i, suicide=True)
            else:
                resource.read(i)

        def worker_write(i, resource):
            """ writing worker """
            time.sleep(random.random() * 2.4)
            print(u"Worker {0} tries to write...".format(i))
            resource.write(i)

        pid = os.getpid()
        print("\nMain process has PID {0}".format(pid))
        jobs = []
        NO_WORKERS = 30
        for i in range(NO_WORKERS):
            if i % 6 == 1:
                p = threadclass(target=worker_write, args=(i, resource))
            else:
                p = threadclass(target=worker_read, args=(i, resource))
            p.start()
            jobs.append(p)

        # wait until all processes have terminated
        while True:
            time.sleep(0.3)
            all_terminated = not max((job.is_alive() for job in jobs))
            if all_terminated:
                break

        # Verify if all locks have been released
        print("Testing if locks have been released...")
        # TODO
        for key in redis_conn.keys():
            if res_name not in key:
                continue
            if (key == 'readcount__{0}'.format(res_name)
                    or key == 'writecount__{0}'.format(res_name)):
                assert(redis_conn[key] == u'0')
            else:
                raise AssertionError("Lock '{0}' has not been released!"
                                     .format(key))


def run():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestLocks)
    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == '__main__':
    run()
