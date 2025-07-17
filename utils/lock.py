import os
import sys
import logging
import atexit
import errno

if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl

logger = logging.getLogger(__name__)
LOCK_FILE_HANDLE = None

def acquire_lock(lock_file_path):
    """
    Acquires an exclusive file lock to prevent multiple application instances.
    
    Creates and locks a file to ensure only one instance of the application
    runs at a time. Uses platform-specific locking mechanisms (fcntl on Unix,
    msvcrt on Windows) and automatically registers cleanup on exit.
    
    Args:
        lock_file_path: Path to the lock file to create/acquire
        
    Returns:
        True if lock was successfully acquired, False if another instance is running
    """
    global LOCK_FILE_HANDLE
    try:
        LOCK_FILE_HANDLE = open(lock_file_path, 'a+', buffering=1)
        if sys.platform == 'win32':
            msvcrt.locking(LOCK_FILE_HANDLE.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.lockf(LOCK_FILE_HANDLE, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        LOCK_FILE_HANDLE.seek(0)
        LOCK_FILE_HANDLE.truncate()
        LOCK_FILE_HANDLE.write(str(os.getpid()))
        LOCK_FILE_HANDLE.flush()
        atexit.register(cleanup_lock_file)
        logger.info(f"Successfully acquired instance lock: {lock_file_path}")
        return True
    except (IOError, OSError) as e:
        is_locked = (sys.platform != 'win32' and e.errno in (errno.EACCES, errno.EAGAIN)) or \
                      (sys.platform == 'win32' and (e.errno == errno.EACCES or 'locked' in str(e).lower()))
        if is_locked:
            logger.error(f"Another instance is already running (Lock file exists: {lock_file_path}). Exiting.")
        else:
            logger.critical(f"Could not create or lock file '{lock_file_path}': {e}. Check permissions. Exiting.")
        if LOCK_FILE_HANDLE:
            LOCK_FILE_HANDLE.close()
        return False
    except Exception as e:
        logger.critical(f"An unexpected error occurred during lock acquisition: {e}. Exiting.", exc_info=True)
        return False

def cleanup_lock_file():
    """
    Releases the file lock and removes the lock file.
    
    This function is automatically called on application exit via atexit.
    It safely releases the platform-specific file lock and removes the
    lock file to allow future instances to start.
    """
    global LOCK_FILE_HANDLE
    if LOCK_FILE_HANDLE:
        lock_file_path = LOCK_FILE_HANDLE.name
        try:
            if sys.platform == 'win32':
                msvcrt.locking(LOCK_FILE_HANDLE.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.lockf(LOCK_FILE_HANDLE, fcntl.LOCK_UN)
            LOCK_FILE_HANDLE.close()
            try:
                os.remove(lock_file_path)
                logger.info(f"Lock file {lock_file_path} cleaned up.")
            except OSError:
                pass
        except Exception as e:
            logger.warning(f"Could not cleanly release lock file: {e}")
        finally:
            LOCK_FILE_HANDLE = None