import arcpy

# workspace settings
arcpy.env.workspace = r'S:\Studies\AP\APF\Swieradow\Swieradow.gdb'
arcpy.env.addOutputsToMap = False
arcpy.env.overwriteOutput = True
pro = arcpy.mp.ArcGISProject("CURRENT")
map = pro.listMaps()[0]

# assigning file paths
results_path = "S:\Studies\AP\APF\\wyniki\\"

hotels = r"S:\Studies\AP\booking\hotels.shp"
restaurants = r"S:\Studies\AP\restauracje\restauracje.shp"
gas_pipeline = r"S:\Studies\AP\Dane_gazociag\gazociag.shp"
lots = r"S:\Studies\AP\Projekt_1_swieradow_dzialki\dzialki_swieradow_egib.shp"
DEM = r"S:\Studies\AP\\nmt.tif"
residential_buildings = r"S:\Studies\AP\BDOT10K\budynki_mieszkalne.shp"
forests = r"S:\Studies\AP\BDOT10K\lasy.shp"
rivers = r"S:\Studies\AP\BDOT10K\rzeki.shp"
roads = r"S:\Studies\AP\BDOT10K\drogi.shp"
surface_water = r"S:\Studies\AP\BDOT10K\wodyPowierzchniowe.shp"
land_cover = r"S:\Studies\AP\BDOT10K\PokrycieTerenu.shp"
study_area_border = r"S:\Studies\AP\Świeradów_granice\Gmina_sw.shp"


# Function to get the variable name for a given value
def get_variable_name(var):
    for name, value in globals().items():
        if value is var:
            return name
    return None
    
    
# Function to create distance map for given parameters
def CreateDistanceMap(inputLayer, minExtreme, maxExtreme, minOptimal, maxOptimal, protZone=False):
    with arcpy.EnvManager(extent=arcpy.Describe(study_area_plus150m).extent):
        dist_map = arcpy.sa.EucDistance(inputLayer, cell_size=5)   
    restricted = arcpy.sa.ExtractByMask(dist_map, study_area_border)
    reclassified = 1
    if minExtreme != minOptimal:
        reclass1 = arcpy.sa.FuzzyMembership(restricted, arcpy.sa.FuzzyLinear(minExtreme, minOptimal))
        reclassified *= reclass1
    if maxExtreme != maxOptimal:
        reclass2 = arcpy.sa.FuzzyMembership(restricted, arcpy.sa.FuzzyLinear(maxExtreme,maxOptimal))
        reclassified *= reclass2
    reclassified.save(results_path + "DistanceMap_" + get_variable_name(inputLayer) + ".tif")
    map.addDataFromPath(results_path + "DistanceMap_" + get_variable_name(inputLayer) + ".tif")
    if protZone:
        strict = restricted >= minExtreme
        strict.save(results_path + "ProtectiveZone_" + get_variable_name(inputLayer) + ".tif")
        map.addDataFromPath(results_path + "ProtectiveZone_" + get_variable_name(inputLayer) + ".tif")
        return strict, reclassified
    return reclassified
    

# Buffer determining the extent of the study area
study_area_plus150m = arcpy.analysis.Buffer(
    in_features=study_area_border,
    out_feature_class= results_path + "gmina_buffer.shp",
    buffer_distance_or_field="150 Meters",
)


#Criterion 1 - distance from residential buildings; not too close, not too far; optimally from 25 to 150 meters
Criterion1 = CreateDistanceMap(residential_buildings, 5, 300, 25, 150)

#Criterion 2 - distance from existing roads; not too close, not too far; optimally from 15 to 100 meters
Criterion2 = CreateDistanceMap(roads, 5, 500, 15, 100)

#Criterion 3 - distance from rivers and water reservoirs; as close as possible; minimum 20 meters (protective zone)
rivers_polygon = arcpy.analysis.Buffer(rivers, results_path + "rivers_buffered.shp", "1 METERS")
water = arcpy.management.Merge([surface_water, rivers_polygon], results_path + "waters.shp")
Criterion3_strict, Criterion3 = CreateDistanceMap(water, 20, 750, 20, 100, True)

#Criterion 4 - slope inclination; as flat as possible; maximum 20%
slope = arcpy.sa.Slope(DEM, "PERCENT_RISE")
slope = arcpy.sa.ExtractByMask(slope, study_area_border)
Criterion4_strict = slope <= 20
Criterion4_strict.save(results_path + "slope_inclination_over20.tif")
map.addDataFromPath(results_path + "slope_inclination_over20.tif")
Criterion4 = arcpy.sa.FuzzyMembership(slope, arcpy.sa.FuzzyLinear(20, 1))
Criterion4.save(results_path + "slope_inclination.tif")
map.addDataFromPath(results_path + "slope_inclination.tif")

#Criterion 5 - sunlight access; optimally southern slopes (SW-SE)
aspect = arcpy.sa.Aspect(DEM)
aspect = arcpy.sa.ExtractByMask(aspect, study_area_border)
East_reclass = arcpy.sa.FuzzyMembership(aspect, arcpy.sa.FuzzyLinear(45, 135))
West_reclass = arcpy.sa.FuzzyMembership(aspect, arcpy.sa.FuzzyLinear(315, 225))
Criterion5 = East_reclass * West_reclass
Criterion5 = arcpy.sa.Con(aspect, 1, Criterion5, "VALUE = -1")
Criterion5.save(results_path + "sunlight_access.tif")
map.addDataFromPath(results_path + "sunlight_access.tif")

#Criterion 6 - distance from the gas pipeline; as far as possible; minimum 25 meters (protective zone)
Criterion6_strict, Criterion6 = CreateDistanceMap(gas_pipeline, 25, 0, 500, 25, True)

 
#Criterion 7 - land coverage; not in the forest
arcpy.management.CalculateField(forests, "Value", "0")
with arcpy.EnvManager(extent=arcpy.Describe(study_area_plus150m).extent):
    Criterion7 = arcpy.conversion.FeatureToRaster(forests, "Value", "fraster", cell_size=5)
Criterion7 = arcpy.sa.Reclassify(Criterion7, "Value", "1 0;NODATA 1")
Criterion7 = arcpy.sa.ExtractByMask(Criterion7, study_area_border)
Criterion7.save(results_path + "forests.tif")
map.addDataFromPath(results_path + "forests.tif")



#Criterion 8 - Good access to the restaurant in the region with the shortest driving time
arcpy.na.MakeServiceAreaAnalysisLayer(
    network_data_source="https://www.arcgis.com/",
    layer_name="restaurants_service_area",
    travel_mode="Czas przejazdu w obszarach wiejskich",
    travel_direction="TO_FACILITIES",
    cutoffs=list(range(1, 16)),
    polygon_detail="HIGH",
    geometry_at_overlaps="SPLIT"
 )
arcpy.na.AddLocations("restaurants_service_area", "Facilities", restaurants)
arcpy.na.Solve("restaurants_service_area","SKIP","TERMINATE")
with arcpy.EnvManager(extent=arcpy.Describe(study_area_plus150m).extent):
    Criterion8 = arcpy.conversion.FeatureToRaster("restaurants_service_area\Polygons", "FromBreak", "raccess")
Criterion8 = arcpy.sa.Reclassify(Criterion8, "Value", "NODATA 15")
Criterion8 = arcpy.sa.FuzzyMembership(Criterion8, arcpy.sa.FuzzyLinear(14, 1))
Criterion8 = arcpy.sa.ExtractByMask(Criterion8, study_area_border)
Criterion8.save(results_path + "restaurants_access.tif")
map.addDataFromPath(results_path + "restaurants_access.tif")


#Criterion 9 - The impact of competition; the least density of high-rated establishments
Criterion9 = arcpy.sa.KernelDensity(hotels, "rating", cell_size=5, in_barriers=study_area_plus150m)
Criterion9 = arcpy.sa.RescaleByFunction(Criterion9, arcpy.sa.TfLogarithm(), 1, 0)
Criterion9 = arcpy.sa.ExtractByMask(Criterion9, study_area_border)
Criterion9.save(results_path + "competition.tif")
map.addDataFromPath(results_path + "competition.tif")

# combination of strict criteria
strict = arcpy.sa.FuzzyOverlay([Criterion7,Criterion6_strict, Criterion4_strict, Criterion3_strict], 'AND')
strict.save(results_path + "Strict_criteria.tif")
map.addDataFromPath(results_path + "Strict_criteria.tif")



#combination of fuzzy criteria with consideration of weights and multiplication by strict criteria.
fuzzy_diff = arcpy.sa.WeightedSum(arcpy.sa.WSTable([[Criterion1, "VALUE", 0.1], [Criterion2, "VALUE",0.2],
                                                            [Criterion3, "VALUE",0.2],[Criterion4, "VALUE", 0.15], 
                                                            [Criterion5, "VALUE",0.1], [Criterion6, "VALUE",0.1], 
                                                            [Criterion8, "VALUE",0.05], [Criterion9, "VALUE", 0.1]]))
fuzzy_diff = fuzzy_diff * strict
fuzzy_diff.save(results_path + "result_diff.tif")
map.addDataFromPath(results_path + "result_diff.tif")                                                            
                                                            
#combination of fuzzy criteria with equal weights and multiplication by strict criteria.                                                            
fuzzy_equal= arcpy.sa.WeightedSum(arcpy.sa.WSTable([[Criterion1, "VALUE", 1/8], [Criterion2, "VALUE", 1/8],
                                                            [Criterion3, "VALUE", 1/8],[Criterion4, "VALUE", 1/8], 
                                                            [Criterion5, "VALUE", 1/8], [Criterion6, "VALUE", 1/8], 
                                                            [Criterion8, "VALUE", 1/8], [Criterion9, "VALUE", 1/8]]))
fuzzy_equal = fuzzy_equal * strict
fuzzy_equal.save(results_path + "result_equal.tif")
map.addDataFromPath(results_path + "result_equal.tif")                                        
                                      
                                      

Final_equal = fuzzy_equal > 0.8
Final_equal.save(results_path + "Final_equal.tif")
map.addDataFromPath(results_path + "Final_equal.tif")

Final_diff = fuzzy_diff > 0.8
Final_diff .save(results_path + "Final_diff .tif")
map.addDataFromPath(results_path + "Final_diff .tif")

equal_polygon = arcpy.conversion.RasterToPolygon(Final_equal, "equal_polygon" ,"NO_SIMPLIFY", "VALUE")
equal_polygon = arcpy.management.SelectLayerByAttribute(equal_polygon, "NEW_SELECTION", "gridcode = 1")
arcpy.analysis.SummarizeWithin(lots, equal_polygon, "se", shape_unit = "SQUAREMETERS")
arcpy.management.CalculateField("se", "utility","!sum_Area_SQUAREMETERS!/!Shape_Area! >= 0.7", "PYTHON3")
lots_equal = arcpy.management.SelectLayerByAttribute("se", "NEW_SELECTION", "utility = '1'")   
dissolved_equal = arcpy.management.Dissolve(lots_equal, results_path + "lots_equal.shp", "#", "#", "SINGLE_PART")
map.addDataFromPath(results_path+ "lots_equal.shp")
 
diff_polygon = arcpy.conversion.RasterToPolygon(Final_diff, "diff_polygon" ,"NO_SIMPLIFY", "VALUE")
diff_polygon = arcpy.management.SelectLayerByAttribute(diff_polygon, "NEW_SELECTION", "gridcode = 1")
arcpy.analysis.SummarizeWithin(lots, diff_polygon, "sw", shape_unit = "SQUAREMETERS")
arcpy.management.CalculateField("sw", "utility","!sum_Area_SQUAREMETERS!/!Shape_Area! >= 0.7", "PYTHON3")    
lots_diff = arcpy.management.SelectLayerByAttribute("sw", "NEW_SELECTION", "utility = '1'")     
dissolved_diff = arcpy.management.Dissolve(lots_diff, results_path + "lots_diff.shp", "#", "#", "SINGLE_PART")
map.addDataFromPath(results_path+ "lots_diff.shp")


#Criterion 10 - land area between 1 and 6 hectares
arcpy.management.CalculateField(dissolved_equal, "Area", "!SHAPE.AREA!", "PYTHON3", '#', "FLOAT")
lots_equal_1h = arcpy.management.SelectLayerByAttribute(dissolved_equal, "NEW_SELECTION", "Area > 10000 AND Area < 60000")
lots_equal_1h = arcpy.management.CopyFeatures(lots_equal_1h, results_path + "lots_equal_1h.shp") 
map.addDataFromPath(results_path+ "lots_equal_1h.shp")

arcpy.management.CalculateField(dissolved_diff, "Area", "!SHAPE.AREA!", "PYTHON3", '#', "FLOAT")
lots_diff_1h = arcpy.management.SelectLayerByAttribute(dissolved_diff, "NEW_SELECTION", "Area > 10000 AND Area < 60000")
lots_diff_1h = arcpy.management.CopyFeatures(lots_diff_1h, results_path + "lots_diff_1h.shp") 
map.addDataFromPath(results_path+ "lots_diff_1h.shp")



#Criterion 11a - shape of the area as compact as possible
lots_equal_1h = arcpy.management.CalculateGeometryAttributes(lots_equal_1h, [["PERIMETER","PERIMETER_LENGTH"]], "METERS")
arcpy.management.CalculateField(lots_equal_1h, "PPscore", "4*math.pi*!AREA!/(!PERIMETER!**2)", "PYTHON3", '#', "FLOAT")
lots_equal_compact = arcpy.management.SelectLayerByAttribute(lots_equal_1h, "NEW_SELECTION", "PPscore > 0.5") 
lots_equal_compact = arcpy.management.CopyFeatures(lots_equal_compact, results_path + "lots_equal_compact.shp") 
map.addDataFromPath(results_path + "lots_equal_compact.shp")

lots_diff_1h = arcpy.management.CalculateGeometryAttributes(lots_diff_1h, [["PERIMETER","PERIMETER_LENGTH"]], "METERS")
arcpy.management.CalculateField(lots_diff_1h, "PPscore", "4*math.pi*!AREA!/(!PERIMETER!**2)", "PYTHON3", '#', "FLOAT")
lots_diff_compact = arcpy.management.SelectLayerByAttribute(lots_diff_1h, "NEW_SELECTION", "PPscore > 0.5") 
lots_diff_compact = arcpy.management.CopyFeatures(lots_diff_compact, results_path + "lots_diff_compact.shp") 
map.addDataFromPath(results_path + "lots_diff_compact.shp")




#Criterion 12 - cost of connetcion to the gas pipeline


# Function made for reclassification (works with BDOT10K only)
codeblock = """
def reclass (kod):
    if kod in ('PTWP01', 'PTWP03', 'PTUT01', 'PTSO01','PTSO02', 'PTWZ01', 'PTWZ02' ):
        return 0
    elif kod in ('PTTR02', 'PTGN01', 'PTGN02', 'PTGN03', 'PTGN04'):
        return 1
    elif kod in ('PTRK01', 'PTRK02'):
        return 15
    elif kod in ('PTUT04', 'PTUT05', 'PTTR01'):
        return 20
    elif kod in ('PTZB05','PTLZ02', 'PTLZ03', 'PTPL01'):
        return 50
    elif kod in ('PTUT02'):
        return 90
    elif kod in ('PTZB02', 'PTLZ01', 'PTUT03', 'PTKM01'):
        return 100
    elif kod in ('PTNZ02', 'PTNZ01', 'PTKM03'):
        return 150
    elif kod in ('PTZB01','PTZB04','PTZB03','PTKM02', 'PTWP02'):
        return 200"""

# Creating relative cost map based on land cover layer
arcpy.management.CalculateField(land_cover, "cost", "reclass(!X_KOD!)", "PYTHON3", codeblock, "FLOAT")
relative_cost_map = arcpy.conversion.FeatureToRaster(land_cover, 'cost', results_path +"relative_cost_map.tif", cell_size = 5)
relative_cost_map = arcpy.sa.Reclassify(relative_cost_map, "Value", "0 NODATA") 
relative_cost_map.save(results_path +"relative_cost_map.tif")
map.addDataFromPath(results_path + "relative_cost_map.tif")     



# Creating cumulative cost maps
cost_dist_equal = arcpy.sa.CostDistance(lots_equal_compact, relative_cost_map, '#', results_path + "cost_dist_equal.tif") 
map.addDataFromPath(results_path + "cost_dist_equal.tif")   
backlink_equal = arcpy.sa.CostBackLink(lots_equal_compact, relative_cost_map, '#', results_path + "backlink_equal.tif") 
map.addDataFromPath(results_path + "backlink_equal.tif")

cost_dist_diff = arcpy.sa.CostDistance(lots_diff_compact, relative_cost_map, '#', results_path + "cost_dist_diff.tif") 
map.addDataFromPath(results_path + "cost_dist_diff.tif")   
backlink_diff = arcpy.sa.CostBackLink(lots_diff_compact, relative_cost_map, '#', results_path + "backlink_diff.tif") 
map.addDataFromPath(results_path + "backlink_diff.tif")



# Determining a parcel with the best possible connection to a gas pipeline
cost_path_equal = arcpy.sa.CostPath(gas_pipeline, cost_dist_equal,  backlink_equal, "BEST_SINGLE"); 
arcpy.conversion.RasterToPolyline(cost_path_equal, results_path + "cost_path_equal.shp")
map.addDataFromPath(results_path+"cost_path_equal.shp")      

cost_path_diff = arcpy.sa.CostPath(gas_pipeline, cost_dist_diff,  backlink_diff, "BEST_SINGLE"); 
arcpy.conversion.RasterToPolyline(cost_path_diff, results_path + "cost_path_diff.shp")
map.addDataFromPath(results_path+"cost_path_diff.shp")       

     
