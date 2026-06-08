class GitOperationError(Exception):
    """Custom exception for git operation failures"""

    pass


class ConfigurationError(Exception):
    """Custom exception for configuration errors"""

    pass


class FileOperationError(Exception):
    """Custom exception for file operation errors"""

    pass


class PackageMaintainerError(Exception):
    """Custom exception for package maintainer loading errors"""

    pass


class PackageError(Exception):
    """Custom exception for package operation failures"""

    pass


class ReleaseCarrierError(Exception):
    """Custom exception for release carrier operation failures"""

    pass


class VersionError(Exception):
    """Custom exception for version operation errors"""

    pass
