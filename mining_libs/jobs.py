from twisted.internet import defer

from stratum import settings
import stratum.logger
log = stratum.logger.get_logger('proxy')

class Job(object):
    def __init__(self):
        self.params = ''

    @classmethod
    def build_from_pool(cls, getWorkParams):
        '''Build job object from Stratum server broadcast'''
        job = Job()
        job.params = getWorkParams
        return job

class JobRegistry(object):
    def __init__(self, f, f1, f2, f3):
        self.f = f
        self.f1 = f1
        self.f2 = f2
        self.f3 = f3
        self.jobs = None
        # stop mining after 6 minutes if internet disconnected
        self.coinTimeout = 360 if settings.COIN=="ETH" else 900
        # Hook for LP broadcasts
        self.on_block = defer.Deferred()

    def replace_job(self, newjob, connection_ref):
        is_main_pool = True
        if self.f and hasattr(self.f, "remote_ip"):
            is_main_pool = connection_ref._get_ip() == self.f.remote_ip

        pool_number = 0
        is_failover_pool1 = False
        if self.f1 and hasattr(self.f1, "remote_ip"):
            is_failover_pool1 = connection_ref._get_ip() == self.f1.remote_ip
            if is_failover_pool1:
                pool_number = 1

        is_failover_pool2 = False
        if self.f2 and hasattr(self.f2, "remote_ip"):
            is_failover_pool2 = connection_ref._get_ip() == self.f2.remote_ip
            if is_failover_pool2:
                pool_number = 2

        is_failover_pool3 = False
        if self.f3 and hasattr(self.f3, "remote_ip"):
            is_failover_pool3 = connection_ref._get_ip() == self.f3.remote_ip
            if is_failover_pool3:
                pool_number = 3

        if is_main_pool:
            log_text = "NEW_JOB MAIN_POOL"
        else:
            log_text = f"NEW_JOB FAILOVER_POOL{pool_number}"

        if (self.f and self.f.is_connected and is_main_pool) or \
                (not self.f.is_connected and not is_main_pool and self.f1 and self.f1.is_connected and is_failover_pool1) or \
                (not self.f.is_connected and not is_main_pool and self.f2 and self.f2.is_connected and is_failover_pool2 and not self.f1.is_connected) or \
                (not self.f.is_connected and not is_main_pool and self.f3 and self.f3.is_connected and is_failover_pool3 and not self.f1.is_connected and not self.f2.is_connected):
            if self.jobs and self.jobs.params and self.jobs.params[0]==newjob.params[0]:
                return
            if stratum.logger.settings.DEBUG:
                log.debug(f"{log_text} {newjob.params}")
            else:
                log.info(log_text)
            self.jobs = newjob
            # Force miners to reload jobs
            on_block = self.on_block
            self.on_block = defer.Deferred()
            on_block.callback(True)
        elif stratum.logger.settings.DEBUG:
            log.debug(f"{log_text} NOT_USED {newjob.params}")

    def submit(self, method, params, worker_name):
        log_text = ""
        if settings.DEBUG:
            log_text = f"{method} by {worker_name} {params}"
        elif method=="eth_submitWork":
            log_text = f"eth_submitWork {params[0]} by {worker_name}"
        if self.f.is_connected:
            if log_text:
                log.info(f"MAIN {log_text}")
            self.f.rpc(method, params, worker_name)
        elif self.f1 and self.f1.is_connected:
            if log_text:
                log.info(f"FAILOVER1 {log_text}")
            self.f1.rpc(method, params, worker_name)
        elif self.f2 and self.f2.is_connected:
            if log_text:
                log.info(f"FAILOVER2 {log_text}")
            self.f2.rpc(method, params, worker_name)
        elif self.f3 and self.f3.is_connected:
            if log_text:
                log.info(f"FAILOVER3 {log_text}")
            self.f3.rpc(method, params, worker_name)
        elif log_text:
            log.info(f"NO_SUBMIT_ALL_POOLS_DOWN {log_text}")
