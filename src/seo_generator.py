# Backward compatibility redirect
try:
    from .common.seo_generator import *
except ImportError:
    from src.common.seo_generator import *
