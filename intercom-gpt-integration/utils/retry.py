import time
import logging
import functools
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

def retry(max_attempts: int = 3, 
          initial_delay: float = 1.0, 
          backoff_factor: float = 2.0, 
          max_delay: float = 30.0,
          exceptions: tuple = (Exception,)) -> Callable:
    """
    A decorator for retrying functions that might fail with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for the delay after each attempt
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exceptions to catch and retry on
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        sleep_time = min(delay, max_delay)
                        logger.warning(f"Attempt {attempt} failed: {str(e)}. Retrying in {sleep_time:.2f}s")
                        time.sleep(sleep_time)
                        delay *= backoff_factor
                    else:
                        logger.error(f"All {max_attempts} attempts failed. Last error: {str(e)}")
            
            # Re-raise the last exception if all attempts failed
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator 
