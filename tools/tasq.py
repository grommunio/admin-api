# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH


import logging
import threading
import queue


logger = logging.getLogger("tasq")


class Task:
    QUEUED = 0  # Stored in database
    LOADED = 1  # Loaded by a TaskQ server
    RUNNING = 2  # Currently not used
    COMPLETED = 3  # Completed successfully
    ERROR = 4  # Error during execution
    CANCELLED = 5  # Cancelled before execution

    _statnames = ("QUEUED", "LOADED", "RUNNING", "COMPLETED", "ERROR", "CANCELLED")

    @property
    def statename(self):
        return self._statnames[self.state] if 0 <= self.state < len(self._statnames) else "UNKNOWN"

    @property
    def done(self):
        """Whether the task is in completed state (either successful or not)."""
        return self.state >= self.COMPLETED

    def __init__(self, ID, command, params, state=LOADED, message=""):
        self.ID = ID
        self.command = command
        self.params = params
        self.state = state
        self.message = message

    def __repr__(self):
        return "<Task #{} ({}) '{}({})'>".format(self.ID, self.statename, self.command, self.params)


class Worker:
    def __init__(self, _queued=None, _finished=None):
        """Start TasQ worker.

        Omitting in- and output queues will not start the main loop,
        allowing to dispatch tasks manually.

        Parameters
        ----------
        _queued : Queue, optional
            Input queue. The default is None.
        _finished : TYPE, optional
            Output queue. The default is None.
        """
        self._queued, self._finished = _queued, _finished
        if None not in (_queued, _finished):
            self.run()
        self.__current = None

    def log(self, level, message):
        if self._finished is None:
            logger.log(logging.getLevelName(level), message)
        else:
            self._finished.put(Task(0, "control", dict(cmd="log", level=level, message=message)))

    def bump(self):
        if self._finished is not None:
            self._finished.put(Task(self.__current.ID, "control", dict(cmd="bump"), message=self.__current.message))

    def dispatch(self, task):
        from time import time
        func = self.cmap.get(task.command)
        if func is None:
            task.state = Task.ERROR
            task.message = "Unknown command '{}'".format(task.command)
        else:
            task.message = None
            try:
                start = time()
                func(self, task)
                duration = time()-start
            except Exception as err:
                import traceback
                self.log("ERROR", traceback.format_exc(5))
                task.state = Task.ERROR
                task.message = " - ".join(str(arg) for arg in err.args)[:160]
        task.state = max(task.state, Task.COMPLETED)
        task.message = task.message or "Completed ({:.1f}ms)".format(1000*duration)
        return task

    def run(self):
        while True:
            self.__current = task = self._queued.get()
            self.dispatch(task)
            self._finished.put(task)
            self.__current = None

    def control(self, task):
        command = task.params.get("cmd")
        if command == "exit":
            raise SystemExit()
        else:
            raise Exception("Invalid or missing control command")

    def debug(self, task):
        command = task.params.get("cmd")
        if command == "bump":
            task.message = task.params.get("message", "Bump")
            self.bump()
            if "t" in task.params:
                import time
                time.wait(task.params["t"])
        elif command == "log":
            self.log(task.params.get("level", "INFO"), task.params.get("message", "(no message specified)"))
        elif command == "task":
            task.message = task.params.get("message", task.message)
            task.state = task.params.get("state", task.state)
        elif command == "wait":
            import time
            time.sleep(task.params.get("t", 5))
        else:
            raise Exception("Invalid or missing test command")

    def deleteFolder(self, task):
        if not {"homedir", "private", "folderID"}.issubset(task.params):
            raise Exception("Missing arguments for delFolder")
        from services import Service
        with Service("exmdb") as exmdb:
            host = task.params.get("homeserver") or exmdb.host
            client = exmdb.ExmdbQueries(host, exmdb.port, task.params["homedir"], task.params["private"])
            client.deleteFolder(task.params["homedir"], task.params["folderID"], task.params.get("clear", False))

    def _ldapSyncUser(self, user, ldap):
        from orm import DB
        from services import ServiceUnavailableError
        from sqlalchemy.exc import IntegrityError
        from tools.DataModel import InvalidAttributeError, MismatchROError
        import traceback
        try:
            userdata = ldap.downsyncUser(user.externID, dict(user.properties.items()))
            if userdata is None:
                return {"ID": user.ID, "username": user.username, "code": 404, "message": "LDAP object not found"}
            user.fromdict(userdata)
            DB.session.commit()
            return {"ID": user.ID, "username": user.username, "code": 200, "message": "Synchronization successful"}
        except (MismatchROError, InvalidAttributeError, ValueError):
            self.log("ERROR", traceback.format_exc(2))
            DB.session.rollback()
            return {"ID": user.ID, "username": user.username, "code": 500, "message": "Synchronization error"}
        except IntegrityError as err:
            self.log("ERROR", traceback.format_exc(2))
            DB.session.rollback()
            return {"ID": user.ID, "username": user.username, "code": 400,
                    "message": "Database integrity error: "+err.orig.args[1]}
        except ServiceUnavailableError as err:
            DB.session.rollback()
            return {"ID": user.ID, "username": user.username, "code": 503, "message": err.args[0]}
        except Exception:
            self.log("ERROR", traceback.format_exc(2))
            DB.session.rollback()
            return {"ID": user.ID, "username": user.username, "code": 500, "message": "Unknown error"}

    def _ldapSyncImportUser(self, candidate, ldap, lang):
        from orm.domains import Domains
        from orm.misc import DBConf
        from orm.users import Users
        from tools.misc import RecursiveDict

        existing = Users.query.filter(Users.username == candidate.email).first()
        if existing:
            if existing.externID == candidate.ID:
                return self.ldapSyncUser(existing, ldap)
            msg = "and is linked to another LDAP object" if existing.externID else "locally"
            return dict(username=candidate.email, code=409, message="User already exists "+msg)

        domain = Domains.query.filter(Domains.domainname == candidate.email.split("@")[1]).with_entities(Domains.ID).first()
        defaults = RecursiveDict({"user": {}, "domain": {}})
        defaults.update(DBConf.getFile("grommunio-admin", "defaults-system", True))
        defaults.update(DBConf.getFile("grommunio-admin", "defaults-domain-"+str(domain.ID)))
        defaults = defaults.get("user", {})

        userdata = ldap.downsyncUser(candidate.ID)
        defaults.update(RecursiveDict(userdata))
        defaults["lang"] = lang or ""
        result, code = Users.create(defaults, externID=candidate.ID)
        if code == 201:
            return dict(ID=result.ID, username=result.username, code=201, message="User created")
        return dict(username=candidate.email, code=code, message=result)

    def _ldapSyncImportContact(self, candidate, ldap, orgID, domains):
        from orm.domains import Domains
        from orm.users import Users
        domains = Domains.query.filter(Domains.orgID == orgID, Domains.ID.in_([domain.ID for domain in domains]))\
                               .with_entities(Domains.ID, Domains.domainname).all()
        existing = Users.query.filter(Users.domainID.in_(domain.ID for domain in domains), Users.externID == candidate.ID)\
                              .with_entities(Users.domainID).all()
        existingDomains = {user.domainID for user in existing}
        domains = [domain for domain in domains if domain.ID not in existingDomains]
        status = []
        for domain in domains:
            contactData = ldap.downsyncUser(candidate.ID)
            contactData["domainID"] = domain.ID
            result, code = Users.mkContact(contactData, candidate.ID)
            if code == 201:
                status.append(dict(ID=result.ID, username=result.username, code=201, message="Contact created"))
            else:
                status.append(dict(username=candidate.email, code=code, message=result))
        return status

    def _ldapSyncImport(self, ldap, orgID, domains, synced, lang, bump):
        syncStatus = []
        candidates = [candidate for candidate in ldap.searchUsers() if candidate.email not in synced]
        domainnames = {domain.domainname for domain in domains}
        for candidate in candidates:
            bump()
            if candidate.type == "contact":
                syncStatus += self._ldapSyncImportContact(candidate, ldap, orgID, domains)
                continue
            if "@" not in candidate.email or (domainnames and candidate.email.split("@", 1)[1] not in domainnames):
                syncStatus.append(dict(username=candidate.email, code=400, message="Invalid domain."))
                continue
            status = self._ldapSyncImportUser(candidate, ldap, lang)
            syncStatus.append(status)
        return syncStatus

    def ldapSync(self, task):
        def bump():
            nonlocal last
            if time.time()-last < updateInterval:
                return
            updateMessage()
            last = time.time()
            self.bump()

        def statusCat(code):
            return "created" if code == 201 else "synced" if code == 200 else "error"

        def updateMessage(task, counts):
            task.message = "{}/{} synced".format(counts["synced"], counts["sync"])
            if counts["created"]:
                task.message += ", {} created".format(counts["created"])
            if counts["error"]:
                task.message += ", {} error{}".format(counts["error"], "" if counts["error"] == 1 else "s")

        from orm.domains import Domains, OrgParam
        from orm.users import Aliases, Users
        from services import Service, ServiceUnavailableError
        import time

        start = last = time.time()
        orgID = task.params.get("orgID")
        domainID = task.params.get("domainID")
        updateInterval = task.params.get("updateInterval", 5)
        Aliases.NTactive(False)
        Users.NTactive(False)

        if domainID is not None:
            domains = Domains.query.filter(Domains.ID == domainID)\
                                   .with_entities(Domains.ID, Domains.domainname, Domains.orgID).all()
            orgIDs = [domains[0].orgID]
            userfilter = [Users.domainID == domainID]
        elif orgID is not None:
            domains = Domains.query.filter(Domains.orgID == orgID).with_entities(Domains.ID, Domains.domainname).all()
            orgIDs = [orgID]
            userfilter = [Users.orgID == orgID]
        else:
            orgIDs = [0]+OrgParam.ldapOrgs()
            domains = None
            userfilter = ()

        users = Users.query.filter(Users.externID != None, *userfilter).all()
        counts = dict(created=0, synced=0, error=0, create=0, sync=len(users))
        syncStatus = []
        synced = set()

        Aliases.NTactive(True)
        Users.NTactive(True)

        for user in users:
            bump()
            try:
                with Service("ldap", user.orgID) as ldap:
                    status = self._ldapSyncUser(user, ldap)
                syncStatus.append(status)
                counts[statusCat(status["code"])] += 1
                if status["code"] == 200:
                    synced.add(user.username)
            except ServiceUnavailableError as err:
                syncStatus.append(dict(ID=user.ID, username=user.username, code=503, message=err.args[0]))
                counts["error"] += 1

        if task.params.get("import"):
            for orgID in orgIDs:
                try:
                    with Service("ldap", orgID) as ldap:
                        status = self._ldapSyncImport(ldap, orgID, domains, synced, task.params.get("lang"), bump)
                    counts["synced"] += sum(1 for s in status if s["code"] == 200)
                    counts["created"] += sum(1 for s in status if s["code"] == 201)
                    counts["error"] += sum(1 for s in status if s["code"] not in (200, 201))
                    syncStatus += status
                except ServiceUnavailableError:
                    pass

        Aliases.NTactive(True)
        Users.NTactive(True)

        updateMessage(task, counts)
        task.message += " ({:.1f}s)".format(time.time()-start)
        task.params["result"] = syncStatus

    cmap = {"control": control, "debug": debug, "delFolder": deleteFolder, "ldapSync": ldapSync}


class TasQServer:
    STOPPED = 0
    STARTING = 1
    STARTED = 2
    STOPPING = 3

    _queued = queue.Queue()
    _finished = queue.Queue()
    _state = STOPPED
    _clerk = None
    _online = True
    _active = {}
    _active_lock = threading.Lock()
    _localID = 0
    _workers = []

    @classmethod
    def _schedule(cls, task):
        with cls._active_lock:
            cls._active[task.ID] = (task, threading.Condition(cls._active_lock))
        cls._queued.put(task)
        return task

    @classmethod
    def create(cls, command, params, synced=True, permission=None, inline=None):
        """Create a new task.

        Parameters
        command : str
            Name of the command
        params : dict
            Command specific parameters
        synced : bool, optional
            Whether to synchronize the task with the database. The default is True.
        permission : PermissionBase, optional
            Restrict access to users with permission. The default is None.
        inline : bool, optional
            Do not execute async, but dispatch in current thread.
            If set to None, only execute inline if TasQ server is not running.
            The default is None.

        Raises
        ------
        ValueError
            Trying to create a "control" command.

        Returns
        -------
        Task
            The created task or None if synced is True and the server is not running.
        """
        if command == "control":
            raise ValueError("Cannot create control commands")
        if inline or (inline is None and not cls.running()):
            return Worker().dispatch(Task(0, command, params))
        elif cls.online() and synced:
            from orm.misc import DB, TasQ
            dbtask = TasQ(dict(command=command, params=params))
            dbtask.state = Task.LOADED if cls.running() else Task.QUEUED
            dbtask.permission = permission
            DB.session.add(dbtask)
            DB.session.commit()
            if cls.running():
                return cls._schedule(Task(dbtask.ID, command, params))
            else:
                return Task(dbtask.ID, command, params)
        else:
            if not cls.running():
                logger.warning("Added local task but TasQ server is not running")
            cls._localID -= 1
            return cls._schedule(Task(cls._localID, command, params))

    @classmethod
    def start(cls, workers=None, online=True):
        """Start the TasQ server.

        Has no effect if the server is already running.

        If procs is None, the number of workers is defined by the
        configuration (default 1).

        Parameters
        ----------
        procs : int, optional
            Number of workers to start. The default is None.
        online : bool, optional
            Whether to run in online mode (tasks are synchronized with the database).
            The default is True.
        """
        if cls._state != cls.STOPPED:
            return
        cls._state = cls.STARTING
        import atexit
        from .config import Config
        atexit.register(cls.stop)
        conf = Config.get("tasq", {})
        workers = workers or conf.get("workers", 1)
        logger.info("Starting TasQ server with {} worker{}".format(workers, "" if workers == 1 else "s"))
        cls._workers = [threading.Thread(target=Worker, args=(cls._queued, cls._finished), name="TasQ Worker")
                        for _ in range(workers)]
        for worker in cls._workers:
            worker.start()
            logger.debug("Started worker with id "+str(worker.ident))
        cls._clerk = threading.Thread(target=cls._process)
        cls._clerk.start()
        cls._online = online
        cls.pull()
        cls._state = cls.STARTED

    @classmethod
    def stop(cls, timeout=None):
        """Stop the TasQ server.

        Parameters
        ----------
        timeout : float, optional
            Maximum number of seconds to wait for worker processes to exit. The default is None.
        """
        if not cls.running():
            return
        cls._state = cls.STOPPING
        from datetime import datetime
        from time import time
        timeout = timeout+time() if timeout is not None else None
        logger.info("Shutting down TasQ server")
        cancelled = []
        try:
            while True:
                cancelled.append(cls._queued.get(False))
        except queue.Empty:
            pass
        for proc in cls._workers:
            cls._queued.put(Task(0, "control", {"cmd": "exit", "dbg": "proc"}))
        with cls._active_lock:
            for task in cancelled:
                if task.ID > 0:
                    from orm.misc import DB, TasQ
                    dbtask = TasQ.query.filter(TasQ.ID == task.ID).first() or \
                             TasQ(dict(command=task.command, params=task.params))
                    dbtask.state = Task.QUEUED
                    dbtask.message = "Restored on TasQ server shutdown"
                    dbtask.updated = datetime.now()
                    DB.session.commit()
                else:
                    task.state = Task.CANCELLED
                    task.message = "TasQ server in offline mode was shut down before task completed"
                tracker = cls._active.pop(task.ID, None)
                if tracker is None:
                    continue
                tracker[0].state = task.state
                tracker[1].message = task.message
                tracker[1].notify_all()
        if len(cancelled):
            logger.info("Putting {} loaded task{} back into the database"
                        .format(len(cancelled), "" if len(cancelled) == 1 else "s"))
        logger.debug("Waiting for workers to exit")
        for proc in cls._workers:
            proc.join(max(timeout-time(), 0) if timeout is not None else None)
        cls._finished.put(Task(0, "control", {"cmd": "exit", "dbg": "thread"}))
        cls._clerk.join()
        cls._state = cls.STOPPED
        logger.info("TasQ server stopped")

    @classmethod
    def online(cls):
        """Try to enable online mode.

        Has no effect if online mode is already enabled or explicitly disabled.

        Returns
        -------
        bool
            Whether the server is now in online mode
        """
        if cls._online is not None:
            return cls._online
        cls._online = True
        return cls.pull() is not None

    @classmethod
    def pull(cls):
        """Import queued tasks from the database.

        Only has an effect if the server is running and in online mode.
        """
        if not cls.running() or not cls._online:
            return 0
        from orm import DB
        from datetime import datetime
        if DB is None or not DB.minVersion(102):
            cls._online = None
            msg = "Database unavailable" if DB is None else "Schema version too old (n102 required)"
            logger.warning(msg + " - falling back to offline mode.")
            return None
        from orm.misc import TasQ
        waiting = TasQ.query.filter(TasQ.state == Task.QUEUED).with_for_update().all()
        for w in waiting:
            if w.command == "control":
                w.state = Task.CANCELLED
                w.message = "Task dropped during import: invalid command"
            else:
                w.state = Task.LOADED
                w.message = "Imported task from database"
            w.updated = datetime.now()
        tasks = [(Task(w.ID, w.command, w.params), w) for w in waiting if w.command != "control"]
        DB.session.commit()
        for task, dbtask in tasks:
            cls._schedule(task)
        logger.info("Pulled {} task{} from database".format(len(tasks), "" if len(tasks) == 1 else "s"))
        return len(tasks)

    @classmethod
    def running(cls):
        """Check if the TasQ server is currently running.

        Returns
        -------
        bool
            Whether the server is running.
        """
        return cls._state in (cls.STARTED, cls.STARTING)

    @classmethod
    def queued(cls):
        """Return number of tasks waiting to be processed."""
        return cls._queued.qsize()

    @classmethod
    def workers(cls):
        """Return number of active worker processes."""
        return sum(1 for proc in cls._workers if proc.is_alive())

    @classmethod
    def wait(cls, taskID, timeout=None):
        """Wait for a task to finish.

        Returns immediately if the is not active.

        The task ID can be retrieved from the task object returned by `create`.

        Parameters
        ----------
        taskID : int
            ID of the task
        timeout : float, optional
            Maximum time (in seconds) to wait for task completion. The default is None.
        """
        with cls._active_lock:
            tracker = cls._active.get(taskID)
            if tracker is not None:
                tracker[1].wait(timeout)

    @classmethod
    def _process(cls):
        logger.debug("Clerk started")
        from datetime import datetime
        while True:
            task = cls._finished.get()
            if task.command == "control":
                if not task.params:
                    continue
                cmd = task.params.get("cmd")
                if cmd == "exit":
                    logger.debug("Clerk stopped")
                    return
                elif cls._online and cmd == "bump":
                    from orm.misc import DB, TasQ
                    dbtask = TasQ.query.filter(TasQ.ID == task.ID).first()
                    if dbtask is not None:
                        dbtask.message = task.message
                        dbtask.updated = datetime.now()
                        DB.session.commit()
                elif cmd == "log":
                    try:
                        logger.log(logging.getLevelName(task.params.get("level", "INFO")),
                                   "<worker> "+task.params.get("message", "(no message specified)"))
                    except Exception:
                        pass
                continue
            with cls._active_lock:
                tracker = cls._active.pop(task.ID, None)
                if cls._online:
                    from orm.misc import DB, TasQ
                    dbtask = TasQ.query.filter(TasQ.ID == task.ID).first()
                    if dbtask is not None:
                        dbtask.state = task.state
                        dbtask.message = task.message
                        dbtask.updated = datetime.now()
                        dbtask.params = task.params
                    DB.session.commit()
                if tracker is not None:
                    tracker[0].state = task.state
                    tracker[0].message = task.message
                    tracker[1].notify_all()
            logger.debug("Task #{} completed ({})".format(task.ID, task.statename))

    class mktask:
        @staticmethod
        def deleteFolder(homedir, folderID, private, clear=False, permission=None, homeserver=None):
            return TasQServer.create("delFolder", dict(homedir=homedir, folderID=folderID, private=private, clear=clear,
                                                       homeserver=homeserver.hostname if homeserver else None),
                                     permission=permission)
