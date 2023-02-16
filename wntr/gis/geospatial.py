"""
The wntr.gis.geospatial module contains functions to snap data and find 
intersects with polygons.
"""

import pandas as pd
import numpy as np

import matplotlib.pylab as plt

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
    closest = closest.sort_values(by=["snap_distance"]) 
       
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
    
    background.plot()
    
    return background


def intersect(A, B, B_value=None, include_background=False, background_value=0):
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
    B_value : str or None (optional)
        Column name in B used to assign a value to each geometry.
        Default is None.
    include_background : bool (optional) 
         Include background, defined as space covered by A that is not covered by B 
         (overlay difference between A and B). The background geometry is added
         to B and is given the name 'BACKGROUND'. Default is False.
    background_value : int or float (optional)
        The value given to background space. This value is used in the intersection 
        statistics if a B_value column name is provided. Default is 0.
        
    Returns
    -------
    pandas DataFrame
        Intersection statistics (index = A.index, columns = defined below)
        Columns include:
            - n: number of intersecting B geometries
            - intersections: list of intersecting B indices
            
        If B_value is given:
            - values: list of intersecting B values
            - sum: sum of the intersecting B values
            - min: minimum of the intersecting B values
            - max: maximum of the intersecting B values
            - mean: mean of the intersecting B values
            
        If A contains Lines and B contains Polygons:
            - weighted_mean: weighted mean of intersecting B values

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
    if isinstance(B_value, str):
        assert B_value in B.columns
    isinstance(include_background, bool)
    isinstance(background_value, (int, float))
    assert A.crs == B.crs
    
    if include_background:
        background = _backgound(A, B)
        if B_value is not None:
            background[B_value] = background_value
        B = pd.concat([B, background])
        
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
    intersects['sort_order'] = 1 # make sure 'BACKGROUND' is listed first
    intersects.loc[intersects['index_right'] == 'BACKGROUND', 'sort_order'] = 0
    intersects.sort_values(['_tmp_index_name', 'sort_order', 'index_right'], inplace=True)
    
    B_indices = intersects.groupby('_tmp_index_name')['index_right'].apply(list)
    B_fraction = intersects.groupby('_tmp_index_name')['intersection_fraction'].apply(list)
    B_n = B_indices.apply(len)
    
    A_index = intersects.index.unique().sort_values()
    stats = pd.DataFrame(index=A_index, 
                         data={'intersections': B_indices,
                               'fraction': B_fraction,
                               'n': B_n})
    
    if B_value is not None:
        stats['values'] = intersects.groupby('_tmp_index_name')[B_value].apply(list)
        stats['sum'] = intersects.groupby('_tmp_index_name')[B_value].sum()
        stats['min'] = intersects.groupby('_tmp_index_name')[B_value].min()
        stats['max'] = intersects.groupby('_tmp_index_name')[B_value].max()
        stats['mean'] = intersects.groupby('_tmp_index_name')[B_value].mean()
        
        if isinstance(stats['fraction'].iloc[0], list):
            # To compute weighted mean, I also tried saving 'values' and 
            # 'fraction' as np.arrays, but those can't be saved to json
            # I thought I could do this without a loop, but the arrays have 
            # different lengths, so operations like np.nansum(x, axis=0) don't 
            # work anyways
            weighted_mean = []
            for i in stats.index:
                val = np.array(stats['values'][i])
                frac = np.array(stats['fraction'][i])
                weighted_mean.append(np.nansum(val*frac)/np.nansum(frac))
            stats['weighted_mean'] = weighted_mean
            
    """    
    # Subset of A that intersects with B
    A_intersects = A.loc[intersects.index.unique().sort_values(),:]
    
    weighted_mean = False
    if (A['geometry'].geom_type).isin(['LineString', 'MultiLineString']).all():
        if (B['geometry'].geom_type).isin(['Polygon', 'MultiPolygon']).all():
            weighted_mean = True
            
    if weighted_mean and B_value is not None:
        weighted_mean = np.array([0.0]*A_intersects.shape[0])
        fraction_background = np.array([0.0]*A_intersects.shape[0])
        A_length = A_intersects.length.values
        covered_length = np.array([0.0]*A_intersects.shape[0])
        index_to_id = dict(zip(A_intersects.index, np.arange(0,A_intersects.shape[0],1)))
        
        for i in B.index:
            Bi = B.loc[[i],:]
            B_geom = gpd.GeoDataFrame(Bi, crs=B.crs)
            A_subset = A_intersects.loc[B_indices.apply(lambda x: i in x),:]
            if A_subset.shape[0] == 0:
                continue
            A_clip = gpd.clip(A_subset, B_geom)
            if A_clip.shape[0] == 0:
                continue
            A_clip_length = A_clip.length
            A_clip_index = A_clip.index
            A_clip_loc = [A_intersects.index.get_loc(i) for i in A_clip_index]
            
            val = Bi.at[i,B_value]
            fraction_length = (A_clip_length/A_length[A_clip_loc]).values
            
            if not np.isnan(val):
                covered_length[A_clip_loc] = covered_length[A_clip_loc] + fraction_length
                weighed_val = fraction_length*val
                weighted_mean[A_clip_loc] = weighted_mean[A_clip_loc] + weighed_val
                
            if B_geom.index[0] == 'BACKGROUND':
                fraction_background[A_clip_loc] = fraction_length
        
        # Normalize weighted mean by covered length (can be over 1 if polygons overlap)
        # Can be less than 1 if there are gaps (when background is not used)
        weighted_mean = weighted_mean/covered_length
        
        stats['weighted_mean'] = weighted_mean
        stats['fraction_background'] = fraction_background
    """
    stats.index.name = None
    
    return stats

def _backgound_original(A, B):
    
    hull_geom = A.unary_union.convex_hull
    hull_data = gpd.GeoDataFrame(pd.DataFrame([{'geometry': hull_geom}]), crs=A.crs)
    
    background_geom = hull_data.overlay(B, how='difference').unary_union
   
    background = gpd.GeoDataFrame(pd.DataFrame([{'geometry': background_geom}]), crs=A.crs)
    background.index = ['BACKGROUND']
    
    return background


def intersect_original(A, B, B_value=None, include_background=False, background_value=0):
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
    B_value : str or None (optional)
        Column name in B used to assign a value to each geometry.
        Default is None.
    include_background : bool (optional) 
         Include background, defined as space covered by A that is not covered by B 
         (overlay difference between A and B). The background geometry is added
         to B and is given the name 'BACKGROUND'. Default is False.
    background_value : int or float (optional)
        The value given to background space. This value is used in the intersection 
        statistics if a B_value column name is provided. Default is 0.
        
    Returns
    -------
    pandas DataFrame
        Intersection statistics (index = A.index, columns = defined below)
        Columns include:
            - n: number of intersecting B geometries
            - intersections: list of intersecting B indices
            
        If B_value is given:
            - values: list of intersecting B values
            - sum: sum of the intersecting B values
            - min: minimum of the intersecting B values
            - max: maximum of the intersecting B values
            - mean: mean of the intersecting B values
            
        If A contains Lines and B contains Polygons:
            - weighted_mean: weighted mean of intersecting B values
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
    if isinstance(B_value, str):
        assert B_value in B.columns
    isinstance(include_background, bool)
    isinstance(background_value, (int, float))
    assert A.crs == B.crs
    
    if include_background:
        background = _backgound_original(A, B)
        if B_value is not None:
            background[B_value] = background_value
        B = pd.concat([B, background])
        
    intersects = gpd.sjoin(A, B, predicate='intersects')
    intersects.index.name = '_tmp_index_name' # set a temp index name for grouping
    
    # Sort values by index and intersecting object
    intersects['sort_order'] = 1 # make sure 'BACKGROUND' is listed first
    intersects.loc[intersects['index_right'] == 'BACKGROUND', 'sort_order'] = 0
    intersects.sort_values(['_tmp_index_name', 'sort_order', 'index_right'], inplace=True)
    
    n = intersects.groupby('_tmp_index_name')['geometry'].count()
    B_indices = intersects.groupby('_tmp_index_name')['index_right'].apply(list)
    #B_indices.sort_values()
    stats = pd.DataFrame(index=A.index, data={'intersections': B_indices,
                                              'n': n,})
    stats['n'] = stats['n'].fillna(0)
    stats['n'] = stats['n'].apply(int)
    stats.loc[stats['intersections'].isnull(), 'intersections'] = stats.loc[stats['intersections'].isnull(), 'intersections'] .apply(lambda x: [])
    
    if B_value is not None:
        stats['values'] = intersects.groupby('_tmp_index_name')[B_value].apply(list)
        stats['sum'] = intersects.groupby('_tmp_index_name')[B_value].sum()
        stats['min'] = intersects.groupby('_tmp_index_name')[B_value].min()
        stats['max'] = intersects.groupby('_tmp_index_name')[B_value].max()
        stats['mean'] = intersects.groupby('_tmp_index_name')[B_value].mean()
        
        stats = stats.reindex(['intersections', 'values', 'n', 'sum', 'min', 'max', 'mean'], axis=1)
        stats.loc[stats['values'].isnull(), 'values'] = stats.loc[stats['values'].isnull(), 'values'] .apply(lambda x: [])
        
    weighted_mean = False
    if (A['geometry'].geom_type).isin(['LineString', 'MultiLineString']).all():
        if (B['geometry'].geom_type).isin(['Polygon', 'MultiPolygon']).all():
            weighted_mean = True
            
    if weighted_mean and B_value is not None:
        stats['weighted_mean'] = 0
        stats['fraction_background'] = 0
        A_length = A.length
        covered_length = pd.Series(0, index = A.index)
        
        for i in B.index:
            B_geom = gpd.GeoDataFrame(B.loc[[i],:], crs=B.crs)
            val = B.loc[i,B_value]
            A_subset = A.loc[stats['intersections'].apply(lambda x: i in x),:]
            #print(i, lines_subset)
            A_clip = gpd.clip(A_subset, B_geom) 
            A_clip_length = A_clip.length
            A_clip_index = A_clip.index
            
            if A_clip_length.shape[0] > 0:
                fraction_length = A_clip_length/A_length[A_clip_index]
                if not np.isnan(val):
                    covered_length[A_clip_index] = covered_length[A_clip_index] + fraction_length
                    weighed_val = fraction_length*val
                    stats.loc[A_clip_index, 'weighted_mean'] = stats.loc[A_clip_index, 'weighted_mean'] + weighed_val
                if B_geom.index[0] == 'BACKGROUND':
                    stats.loc[A_clip_index, 'fraction_background'] = fraction_length
        
        # Normalize weighted mean by covered length (can be over 1 if polygons overlap)
        # Can be less than 1 if there are gaps (when background is not used)
        stats['weighted_mean'] = stats['weighted_mean']/covered_length
        
        # Covered_length is NaN if length A is 0, set weighted mean to mean
        stats.loc[covered_length.isna(), 'weighted_mean'] = stats.loc[covered_length.isna(), 'mean']
        
        # No intersection, set weighted mean to NaN
        stats.loc[stats['n']==0, 'weighted_mean'] = np.NaN
        
    stats.index.name = None
    
    return stats