"""
The wntr.gis.geospatial module contains functions to snap data and find 
intersects with polygons.
"""

import pandas as pd
import numpy as np

try:
    from shapely.geometry import MultiPoint, LineString, Point, shape
    has_shapely = True
except ModuleNotFoundError:
    has_shapely = False

try:
    import geopandas as gpd
    has_geopandas = True
except ModuleNotFoundError:
    gpd = None
    has_geopandas = False


def snap(A, B, tolerance):  
    """
    Snap Points in A to Points or Lines in B

    For each Point geometry in A, the function returns snapped Point geometry 
    and associated element in B. Note the CRS of A must equal the CRS of B.
    
    Parameters
    ----------
    A : geopandas GeoDataFrame
        GeoDataFrame containing Point geometries.
    B : geopandas GeoDataFrame
        GeoDataFrame containing Point, LineString, or MultiLineString geometries.
    tolerance : float
        Maximum allowable distance (in the coordinate reference system units) 
        between Points in A and Points or Lines in B.  
    
    Returns
    -------
    GeoPandas GeoDataFrame
        Snapped points (index = A.index, columns = defined below)
        
        If B contains Points, columns include:
            - node: closest Point in B to Point in A
            - snap_distance: distance between Point in A and snapped point
            - geometry: GeoPandas Point object of the snapped point
        
        If B contains Lines or MultiLineString, columns include:
            - link: closest Line in B to Point in A
            - node: start or end node of Line in B that is closest to the snapped point (if B contains columns "start_node_name" and "end_node_name")
            - snap_distance: distance between Point A and snapped point
            - line_position: normalized distance of snapped point along Line in B from the start node (0.0) and end node (1.0)
            - geometry: GeoPandas Point object of the snapped point
    """   
    if not has_shapely or not has_geopandas:
        raise ModuleNotFoundError('shapley and geopandas are required')
        
    isinstance(A, gpd.GeoDataFrame)
    assert(A['geometry'].geom_type).isin(['Point']).all()
    isinstance(B, gpd.GeoDataFrame)
    assert (B['geometry'].geom_type).isin(['Point', 'LineString', 'MultiLineString']).all()
    assert A.crs == B.crs
    
    # Modify B to include "indexB" as a separate column
    B = B.reset_index()
    B.rename(columns={'index':'indexB'}, inplace=True)
    
    # Define the coordinate reference system, based on B
    crs = B.crs
    
    # Determine which Bs are closest to each A
    bbox = A.bounds + [-tolerance, -tolerance, tolerance, tolerance]       
    hits = bbox.apply(lambda row: list(B.loc[list(B.sindex.intersection(row))]['indexB']), axis=1)        
    closest = pd.DataFrame({
        # index of points table
        "point": np.repeat(hits.index, hits.apply(len)),
        # name of link
        "indexB": np.concatenate(hits.values)
        })
    
    # Merge the closest dataframe with the lines dataframe on the line names
    closest = pd.merge(closest, B, on="indexB")

    # Join back to the original points to get their geometry
    # rename the point geometry as "points"
    closest = closest.join(A.geometry.rename("points"), on="point")
    
    # Convert back to a GeoDataFrame, so we can do spatial ops
    closest = gpd.GeoDataFrame(closest, geometry="geometry", crs=crs)  
    
    # Calculate distance between the point and nearby links
    closest["snap_distance"] = closest.geometry.distance(gpd.GeoSeries(closest.points, crs=crs))
        
    # Collect only point/link pairs within snap distance radius
    # This is needed because B.sindex.intersection(row) above can return false positives
    closest = closest[closest['snap_distance'] <= tolerance]
    
    # Sort on ascending snap distance, so that closest goes to top
    closest = closest.sort_values(by=["snap_distance", "indexB"]) 
       
    # group by the index of the points and take the first, which is the closest line
    closest = closest.groupby("point").first()      
    
    # construct a GeoDataFrame of the closest elements of B
    closest = gpd.GeoDataFrame(closest, geometry="geometry", crs=crs)
    
    # Reset B index
    B.set_index('indexB', inplace=True)
    B.index.name = None
    
    # snap to points
    if B['geometry'].geom_type.isin(['Point']).all():
        snapped_points = closest.rename(columns={"indexB":"node"})
        snapped_points = snapped_points[["node", "snap_distance", "geometry"]]
        snapped_points.index.name = None      
        
    # snap to lines
    if B['geometry'].geom_type.isin(['LineString', 'MultiLineString']).all():
        closest = closest.rename(columns={"indexB":"link"})        
        # position of nearest point from start of the line
        pos = closest.geometry.project(gpd.GeoSeries(closest.points))        
        # get new point location geometry
        snapped_points = closest.geometry.interpolate(pos)
        snapped_points = gpd.GeoDataFrame(data=closest ,geometry=snapped_points, crs=crs)
        # determine whether the snapped point is closer to the start or end node
        snapped_points["line_position"] = closest.geometry.project(snapped_points, normalized=True)
        if ("start_node_name" in closest.columns) and ("end_node_name" in closest.columns):
            snapped_points.loc[snapped_points["line_position"]<0.5, "node"] = closest["start_node_name"]
            snapped_points.loc[snapped_points["line_position"]>=0.5, "node"] = closest["end_node_name"]
            snapped_points = snapped_points[["link", "node", "snap_distance", "line_position", "geometry"]]
        else:
            snapped_points = snapped_points[["link", "snap_distance", "line_position", "geometry"]]
        snapped_points.index.name = None
        
    return snapped_points

def _backgound(A, B):
    
    """
    hull_geom = A.unary_union.convex_hull

    hull_data = gpd.GeoDataFrame(pd.DataFrame([{'geometry': hull_geom}]), crs=A.crs)
    
    background_geom = hull_data.overlay(B, how='difference').unary_union
   
    background = gpd.GeoDataFrame(pd.DataFrame([{'geometry': background_geom}]), crs=A.crs)
    background.index = ['BACKGROUND']
    """
    Ai_hull = gpd.GeoSeries([A.unary_union.envelope], crs=A.crs)
    Bi = gpd.GeoSeries([B.unary_union], crs=B.crs)
    background = Ai_hull.difference(Bi)
    background = background.to_frame('geometry')
    background.index = ['BACKGROUND']
    
    # background.plot()
    
    return background


def intersect(A, B, attributes=None, include_background=False):
    """
    Intersect Points, Lines or Polygons in A with Points, Lines, or Polygons in B.
    Return statistics on the intersection.
    
    The function returns information about the intersection for each geometry 
    in A. Each geometry in B is assigned a value based on a column of data in 
    that GeoDataFrame.  Note the CRS of A must equal the CRS of B.
    
    Parameters
    ----------
    A : geopandas GeoDataFrame
        GeoDataFrame containing Point, LineString, or Polygon geometries
    B : geopandas GeoDataFrame
        GeoDataFrame containing  Point, LineString, or Polygon geometries
    attributes : list or None (optional)
        List of column names in B used to assign a value to each geometry.
        Default is None.
    include_background : bool (optional) 
         Include background, defined as space covered by A that is not covered by B 
         (overlay difference between A and B). The background geometry is added
         to B and is given the name 'BACKGROUND'. Default is False.
        
    Returns
    -------
    pandas DataFrame
        Intersection statistics (index = A.index, columns = defined below)
        Columns include:
            - intersections: list of intersecting B indices
            - fraction: list with fraction of A that intersects B
            - n: number of intersecting B geometries
            - for each attribute: list of attribute values
    """
    if not has_shapely or not has_geopandas:
        raise ModuleNotFoundError('shapley and geopandas are required')
        
    isinstance(A, gpd.GeoDataFrame)
    assert (A['geometry'].geom_type).isin(['Point', 'LineString', 
                                           'MultiLineString', 'Polygon', 
                                           'MultiPolygon']).all()
    isinstance(B, gpd.GeoDataFrame)
    assert (B['geometry'].geom_type).isin(['Point', 'LineString', 
                                           'MultiLineString', 'Polygon', 
                                           'MultiPolygon']).all()
    if isinstance(attributes, list):
        for B_value in attributes:
            assert B_value in B.columns
    isinstance(include_background, bool)
    assert A.crs == B.crs
    
    if include_background:
        background = _backgound(A, B)
        B = pd.concat([B, background])
        
    original_A_index = A.index
    A = A.reset_index(drop=True)
    
    original_B_index = B.index
    B = B.reset_index(drop=True)

    intersects = gpd.sjoin(A, B, predicate='intersects')
    
    Ai = intersects.loc[:,'geometry'].reset_index()
    Bi = B.loc[intersects['index_right'], 'geometry'].reset_index()
    intersect_geom = Ai.intersection(Bi)
    if (A['geometry'].geom_type).isin(['LineString', 'MultiLineString']).all():
        fraction = intersect_geom.length/Ai.length
    elif (A['geometry'].geom_type).isin(['Polygon', 'MultiPolygon']).all():
        fraction = intersect_geom.area/Ai.area
    else: # Point geometry, no fraction
        fraction = pd.Series(None, index=Ai.index) 
    intersects['intersection_geometry'] = intersect_geom.values
    intersects['intersection_fraction'] = fraction.round(3).values
    
    intersects.index.name = '_tmp_index_name' # set a temp index name for grouping
    
    # Sort values by index and intersecting object
    intersects.sort_values(['_tmp_index_name', 'index_right'], inplace=True)
    
    # bring original B indices back for B_indices list
    # intersects.index_right = intersects.index_right.apply(lambda x: "BACKGROUND" if x == "BACKGROUND" else original_A_index[x]) 
    intersects.index_right = intersects.index_right.apply(lambda x: original_B_index[x]) 
    B_indices = intersects.groupby('_tmp_index_name')['index_right'].apply(list)
    B_fraction = intersects.groupby('_tmp_index_name')['intersection_fraction'].apply(list)
    B_n = B_indices.apply(len)
    
    A_index = intersects.index.unique().sort_values()
    results = pd.DataFrame(index=A_index, 
                           data={'intersections': B_indices,
                                 'fraction': B_fraction,
                                 'n': B_n})
    
    if isinstance(attributes, list):
        for B_value in attributes:
            results[B_value] = intersects.groupby('_tmp_index_name')[B_value].apply(list)

    # replace original indices and remove tmp_index_name
    A.index = original_A_index
    B.index = original_B_index
    results.index = original_A_index[results.index]
    
    return results


def intersect_filter_rows(intersect, entry, operation, fraction_threshold):
    """
    Keep row if entry in `intersections` meets `fraction` threshold criteria
    
    Parameters
    ----------
    intersect: pd.DataFrame
        output from intersect
    entry: str, int, or float
        name of entry in `intersections` column
    operation: numpy operator
        Numpy operator, options include
        np.greater,
        np.greater_equal,
        np.less,
        np.less_equal,
        np.equal,
        np.not_equal
    fraction_threshold: float
        Filter value
    """
    assert all([i in intersect.columns for i in ['intersections', 'fraction']])
    assert isinstance(intersect['intersections'].iloc[0], list)
    assert isinstance(intersect['fraction'].iloc[0], list)
    
    mask = []
    for i, row in intersect.iterrows():
        key_i = np.where(np.array(row['intersections']) == entry)[0]
        if len(key_i) > 0:
            keep = operation(row['fraction'][key_i[0]], fraction_threshold)
            mask.append(keep)
        else:
            mask.append(True)
            
    return intersect.loc[mask,:]
    

def intersect_stats(intersect, attribute, fraction_threshold=None, nan_value=None):
    """
    Compute stats on an attribute of intersections.  
    Apply a fraction threshold and fill nan values if needed.
    """
    assert all([i in intersect.columns for i in ['intersections', 'fraction', attribute]])
    assert isinstance(intersect['intersections'].iloc[0], list)
    assert isinstance(intersect['fraction'].iloc[0], list)
    assert isinstance(intersect[attribute].iloc[0], list)

    stats = {'intersections': [], 'fraction': [], 'n': [], attribute: [], 
             'sum': [], 'min': [], 'max': [], 'mean': [], 'weighted_mean': []}

    for i in intersect.index:
        val = np.array(intersect[attribute][i])
        frac = np.array(intersect['fraction'][i])
        inter = np.array(intersect['intersections'][i])
        
        if isinstance(fraction_threshold, (int, float)):
            mask = (frac >= fraction_threshold)
            val = val[mask]
            frac = frac[mask]
            inter = inter[mask]
        
        stats['intersections'].append(inter)
        stats['fraction'].append(frac)
        stats['n'].append(len(inter))
        stats[attribute].append(val)

        if nan_value is not None:
            np.nan_to_num(val, copy=False, nan=nan_value)
            
        if len(val) > 0:
            stats['sum'].append(np.nansum(val))
            stats['min'].append(np.nanmin(val))
            stats['max'].append(np.nanmax(val))
            stats['mean'].append(np.nanmean(val))
            stats['weighted_mean'].append(np.nansum(val*frac)/np.nansum(frac[~np.isnan(val)]))
        else:
            stats['sum'].append(None)
            stats['min'].append(None)
            stats['max'].append(None)
            stats['mean'].append(None)
            stats['weighted_mean'].append(None)
    
    stats = pd.DataFrame(stats, index=intersect.index)

    return stats
