from typing import Union
from pathlib import Path

from osmnx.features import features_from_polygon, features_from_xml
from osmnx import settings
from geopandas import clip, GeoDataFrame
from shapely.geometry import Polygon

from prettymapp.geo import explode_multigeometries
from prettymapp.settings import LC_SETTINGS

settings.use_cache = True
settings.log_console = False


def get_osm_tags():
    """
    Get relevant OSM tags for use with prettymapp
    """
    tags: dict = {}
    for d in LC_SETTINGS.values():  # type: ignore
        for k, v in d.items():  # type: ignore
            try:
                tags.setdefault(k, []).extend(v)
            except TypeError:  # e.g. "building": True
                tags[k] = v
    return tags


def cleanup_osm_df(df: GeoDataFrame, aoi: Polygon) -> GeoDataFrame:
    """
    Cleanup of queried osm geometries to relevant level for use with prettymapp
    """
    df = df.droplevel(level=0)
    df = df[~df.geometry.geom_type.isin(["Point", "MultiPoint"])]

    df = clip(df, aoi)
    df = explode_multigeometries(df)

    df["landcover_class"] = None
    for lc_class, osm_tags in LC_SETTINGS.items():
        tags_in_columns = list(set(osm_tags.keys()).intersection(list(df.columns)))  # type: ignore
        mask_lc_class = df[tags_in_columns].notna().sum(axis=1) != 0
        # Remove mask elements that belong to other subtag
        listed_osm_tags = {
            k: v
            for k, v in osm_tags.items()  # type: ignore
            if isinstance(v, list) and k in tags_in_columns
        }
        for tag, subtags in listed_osm_tags.items():
            mask_from_different_subtag = ~df[tag].isin(subtags) & df[tag].notna()
            mask_lc_class[mask_from_different_subtag] = False
        df.loc[mask_lc_class, "landcover_class"] = lc_class
    # Drop not assigned elements (part of multiple classes)
    df = df[~df["landcover_class"].isnull()]
    df = df.drop(
        df.columns.difference(["geometry", "landcover_class", "highway"]), axis=1
    )

    return df


def get_osm_geometries(aoi: Polygon) -> GeoDataFrame:
    """
    Query OSM features within a polygon geometry.

    Args:
        aoi: Polygon geometry query boundary.
    """
    tags = get_osm_tags()
    df = features_from_polygon(polygon=aoi, tags=tags)
    df = cleanup_osm_df(df, aoi)
    return df


def get_osm_geometries_from_xml(filepath: Union[str, Path], aoi: Union[Polygon, None]=None) -> GeoDataFrame:
    """
    Query OSM features in an OSM-formatted XML file.

    Args:
        filepath: path to file containing OSM XML data
        aoi: Optional geographic boundary to filter elements
    """
    tags = get_osm_tags()
    df = features_from_xml(filepath, polygon=aoi, tags=tags)
    df = cleanup_osm_df(df, aoi)
    return df
