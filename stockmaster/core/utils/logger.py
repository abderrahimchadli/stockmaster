import logging

# Create a logger for the application
logger = logging.getLogger('stockmaster')

# Don't propagate to root logger
logger.propagate = False

# Create a custom formatter for the logger
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create a handler for the logger (console handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(console_handler)

# Set the default log level (can be overridden by settings)
logger.setLevel(logging.INFO)