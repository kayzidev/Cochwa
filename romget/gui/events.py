"""Les workers ne touchent jamais Tcl/Tk ; les callbacks sont consommés par la GUI."""

from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue


class Dispatcher:
    def __init__(self, root, on_error):
        self.root = root
        self.on_error = on_error
        self.events = Queue()
        self.closed = False
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ui-work")
        self.pending = set()
        self.timer = root.after(50, self.drain)

    def submit(self, work, success, error=None):
        if self.closed:
            return
        if len(self.pending) >= 64:
            (error or self.on_error)("Trop de tâches en attente ; réessayer après le chargement")
            return
        future = self.pool.submit(work)
        self.pending.add(future)

        def done(result):
            try:
                self.events.put((success, result.result(), result))
            except Exception as exc:
                self.events.put((error or self.on_error, str(exc), result))

        future.add_done_callback(done)

    def post(self, callback, value=None):
        if not self.closed:
            self.events.put((callback, value, None))

    def drain(self):
        if self.closed:
            return
        for _ in range(50):
            try:
                callback, value, future = self.events.get_nowait()
            except Empty:
                break
            if future:
                self.pending.discard(future)
            try:
                callback(value)
            except Exception as exc:
                self.on_error(str(exc))
        self.timer = self.root.after(50, self.drain)

    def close(self):
        self.closed = True
        self.root.after_cancel(self.timer)
        self.pool.shutdown(wait=False, cancel_futures=True)
