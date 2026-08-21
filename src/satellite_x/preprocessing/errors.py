"""Set 2 preprocessing failures."""


class PreprocessingError(Exception):
    pass


class SceneCatalogError(PreprocessingError):
    pass


class RasterQualityError(PreprocessingError):
    pass
