from ndex2.nice_cx_network import NiceCXNetwork
from lxml import etree as ET
import os
import ndex2
import pprint

# import ndex2.client as nc
# import networkx as nx

NAMESPACES = {
    "ns1": "http://www.wso2.org/php/xsd",
    "ns2": "http://www.wikipathways.org/webservice/",
    "ns3": "http://pathvisio.org/GPML/2013a",
}

NDEX_USER = os.environ["NDEX_USER"]
NDEX_PWD = os.environ["NDEX_PWD"]

entities_by_id = dict()
group_id_to_entity_id = dict()
group_contents_by_group_id = dict()
dummy_entities = list()

# read gpml file
# gpml_file = "sample.gpml"
gpml_file = "complex.gpml"
# gpml_file = "WP289_102527.gpml"
dom = ET.parse(gpml_file)

cx_network = NiceCXNetwork()
gpml_pathway = dom.getroot()
cx_network.set_name(gpml_pathway.get("Name"))
cartesianLayout = []


class GraphIdManager:
    """
    Based on this code in JS:
    https://github.com/wikipathways/gpml2pvjson-js/blob/91820459b2fa885406d4f2e6a8059ac43e80fa62/src/GraphIdManager.ts
    Generates a new graph_id
    """

    def __init__(self):
        self.incrementing_value_as_int = int("0xa00", base=16)
        self.namespace = "gpml2cxgeneratedid"

    def generate_and_record(self):
        """
        Generate a new GraphId (one not found in the source GPML)
        """
        self.incrementing_value_as_int += 1
        # NOTE: the namespace is not part of incrementing_value_as_int
        return self.namespace + hex(self.incrementing_value_as_int)


#    def record_existing(self, graph_id_as_hex):
#        """
#        Recognize the existence of a GraphId found in the source GPML.
#        TODO: what's the point of this? Since we're using a namespace,
#        why increment for other namespaces?
#        """
#        incrementing_value_as_int = self.incrementing_value_as_int
#        graph_id_as_int = int(graph_id_as_hex, base=16)
#        # NOTE: this graphIdAsInt does not refer to exactly the same thing as PathVisio's
#        # IncrementingValue, because it's the sum of RandomValue and IncrementingValue.
#        if graph_id_as_int > incrementing_value_as_int:
#            self.incrementing_value_as_int = graph_id_as_int


def set_cartesian_layout_aspect(self, cartesian_layout_aspect):
    """
    Replaces existing cartesian layout with data passed in.
    This method will update meta data and remove all cartesian
    layout aspects setting the new data to :py:const:`cartesianLayout`
    :param cartesian_layout_aspect:
    :return:
    """
    if cartesian_layout_aspect is None:
        raise TypeError("Cartesian Layout aspect is None")

    self.set_opaque_aspect("cartesianLayout", cartesian_layout_aspect)

    mde = {
        "name": "cartesianLayout",
        "elementCount": len(cartesian_layout_aspect),
        "version": "1.0",
        "consistencyGroup": 1,
        "properties": [],
    }
    self.metadata["cartesianLayout"] = mde


def set_visual_properties_aspect(self, visual_props_aspect):
    """
    Replaces existing visual properties with data passed in.
    This method will update meta data and remove all visual aspects
    setting the new data to :py:const:`~.NiceCXNetwork.CY_VISUAL_PROPERTIES`
    aspect
    :param visual_props_aspect:
    :return:
    """
    if visual_props_aspect is None:
        raise TypeError("Visual Properties aspect is None")

    self._delete_deprecated_visual_properties_aspect()
    self.set_opaque_aspect(NiceCXNetwork.CY_VISUAL_PROPERTIES, visual_props_aspect)

    mde = {
        "name": "cyVisualProperties",
        "elementCount": len(visual_props_aspect),
        "version": "1.0",
        "consistencyGroup": 1,
        #        "properties": [
        #            {
        #                "properties_of": "nodes:default",
        #                "properties": {"NODE_SHAPE": "RECTANGLE"},
        #            }
        #        ],
        "properties": [],
        # "properties": visual_props_aspect,
    }
    self.metadata[NiceCXNetwork.CY_VISUAL_PROPERTIES] = mde


color_keys = ("Color", "FillColor")

shape_mappings = {
    "RoundedRectangle": "RoundRectangle",
    "Pentagon": "Hexagon",
    "None": "",
    "Oval": "Ellipse",
}


def process_kv(gpml_key, gpml_value):
    cx_key = gpml_key
    cx_value = gpml_value
    if gpml_key == "ShapeType":
        cx_key = "Shape"
        if gpml_key in shape_mappings:
            cx_value = shape_mappings[gpml_value]
    elif gpml_key in color_keys:
        cx_value = "#" + gpml_value

    return {"key": cx_key, "value": cx_value}


def get_numeric_coordinate(s):
    result = 0
    if isinstance(s, int) or isinstance(s, float):
        result = s
    elif isinstance(s, str) and s.replace(".", "", 1).isdigit():
        result = float(s)

    return result


def add_cx_entity_from_gpml(self, gpml_entity):
    graph_id = gpml_entity.get("GraphId")
    group_ref = gpml_entity.get("GroupRef")
    if group_ref is not None:
        self.add_node_attribute(
            property_of=cx_node, name="GroupRef", values=group_ref, subnetwork=group_ref
        )
        if group_ref not in group_contents_by_group_id:
            group_contents_by_group_id[group_ref] = []
            group_contents_by_group_id[group_ref].append(graph_id)


def add_cx_node_from_gpml(self, gpml_node):
    add_cx_entity_from_gpml(self, gpml_node)
    graph_id = gpml_node.get("GraphId")
    cx_node = self.create_node(node_name=graph_id)
    entities_by_id[graph_id] = cx_node

    #    group_ref = gpml_node.get("GroupRef")
    #    if group_ref is not None:
    #        self.add_node_attribute(property_of=cx_node, name="GroupRef", values=group_ref, subnetwork=group_ref)

    # TODO: some GPML elements have default ShapeType of Rectangle, but
    # the default Shape for CX is Ellipse.
    self.add_node_attribute(property_of=cx_node, name="Shape", values="Rectangle")

    text_label = gpml_node.get("TextLabel")
    if text_label:
        self.add_node_attribute(
            property_of=cx_node, name="shared name", values=text_label
        )
    for name, value in sorted(gpml_node.items()):
        kv = process_kv(name, value)
        self.add_node_attribute(property_of=cx_node, name=kv["key"], values=kv["value"])
    for graphics in gpml_node.findall("ns3:Graphics", NAMESPACES):
        # TODO: what do x and y mean in CX? Center or top-left?
        center_x = graphics.get("CenterX")
        center_y = graphics.get("CenterY")
        zorder = graphics.get("ZOrder")
        cartesianLayout.append(
            {
                "node": cx_node,
                "x": get_numeric_coordinate(center_x),
                "y": get_numeric_coordinate(center_y),
                "z": get_numeric_coordinate(zorder),
            }
        )
        for name, value in sorted(graphics.items()):
            kv = process_kv(name, value)
            self.add_node_attribute(
                property_of=cx_node, name=kv["key"], values=kv["value"]
            )


def add_anchors(self, gpml_edge):
    for graphics in gpml_edge.findall("ns3:Graphics", NAMESPACES):
        for anchor in graphics.findall("ns3:Anchor", NAMESPACES):
            add_cx_node_from_gpml(self, anchor)


def add_cx_edge_from_gpml(self, gpml_edge):
    add_cx_entity_from_gpml(self, gpml_edge)
    # graph_id = gpml_edge.get("GraphId")
    # edge_attributes = dict()
    for graphics in gpml_edge.findall("ns3:Graphics", NAMESPACES):
        point_graph_ids = list()
        for point in graphics.findall("ns3:Point", NAMESPACES):
            GraphRef = point.get("GraphRef")
            point_graph_ids.append(GraphRef)

        start_end_point_graph_ids = list([point_graph_ids[0], point_graph_ids[-1]])
        start_end_points = list()
        for point_graph_id in start_end_point_graph_ids:
            point_id = point_graph_id
            if point_graph_id is None:
                dummy_entity_id = "dummy%r" % len(dummy_entities)
                dummy_entities.append(dummy_entity_id)
                cx_node = self.create_node(node_name=dummy_entity_id)
                entities_by_id[dummy_entity_id] = cx_node
                point_id = dummy_entity_id
            start_end_points.append(entities_by_id[point_id])

        cx_edge = self.create_edge(
            edge_source=start_end_points[0],
            edge_target=start_end_points[-1],
            edge_interaction="interacts-with",
        )

        for name, value in sorted(graphics.items()):
            self.add_edge_attribute(property_of=cx_edge, name=name, values=value)


graph_id_manager = GraphIdManager()

for gpml_node in dom.findall("ns3:Group", NAMESPACES):
    # add_cx_node_from_gpml(cx_network, gpml_node)
    group_id = gpml_node.get("GroupId")
    graph_id = gpml_node.get("GraphId")
    if graph_id is None:
        graph_id = graph_id_manager.generate_and_record()
    cx_node = cx_network.create_node(node_name=graph_id)
    entities_by_id[graph_id] = cx_node
    group_id_to_entity_id[group_id] = cx_node

    # TODO: some GPML elements have default ShapeType of Rectangle, but
    # the default Shape for CX is Ellipse.
    cx_network.add_node_attribute(property_of=cx_node, name="Shape", values="Rectangle")

    #    text_label = gpml_node.get("TextLabel")
    #    if text_label:
    #        cx_network.add_node_attribute(
    #            property_of=cx_node, name="shared name", values=text_label
    #        )
    for name, value in sorted(gpml_node.items()):
        kv = process_kv(name, value)
        cx_network.add_node_attribute(
            property_of=cx_node, name=kv["key"], values=kv["value"]
        )

for gpml_node in dom.findall("ns3:DataNode", NAMESPACES):
    add_cx_node_from_gpml(cx_network, gpml_node)

for gpml_node in dom.findall("ns3:Shape", NAMESPACES):
    add_cx_node_from_gpml(cx_network, gpml_node)

for gpml_node in dom.findall("ns3:Label", NAMESPACES):
    add_cx_node_from_gpml(cx_network, gpml_node)

for gpml_edge in dom.findall("ns3:Interaction", NAMESPACES):
    add_anchors(cx_network, gpml_edge)

for gpml_edge in dom.findall("ns3:GraphicalLine", NAMESPACES):
    add_anchors(cx_network, gpml_edge)

for gpml_edge in dom.findall("ns3:Interaction", NAMESPACES):
    add_cx_edge_from_gpml(cx_network, gpml_edge)

for gpml_edge in dom.findall("ns3:GraphicalLine", NAMESPACES):
    add_cx_edge_from_gpml(cx_network, gpml_edge)

for group_id, group_contents in group_contents_by_group_id.items():
    cx_node = group_id_to_entity_id[group_id]
    # TODO: calculate the actual values
    min_x = 10
    max_x = 100
    min_y = 10
    max_y = 100
    min_z = 100

    width = max_x - min_x
    height = max_y - min_y

    cartesianLayout.append(
        {
            "node": cx_node,
            "x": get_numeric_coordinate(min_x),
            "y": get_numeric_coordinate(min_y),
            "z": get_numeric_coordinate(min_z),
        }
    )

    # cx_network.add_node_attribute(property_of=cx_node, name="X", values=min_x)
    # cx_network.add_node_attribute(property_of=cx_node, name="Y", values=min_y)
    cx_network.add_node_attribute(property_of=cx_node, name="WIDTH", values=width)
    cx_network.add_node_attribute(property_of=cx_node, name="HEIGHT", values=height)

# TODO: need to handle defaults. The following doesn't appear to work.
# node_properties = [
#    {"properties_of": "nodes:default", "properties": {"NODE_SHAPE": "RECTANGLE"}}
# ]
# set_visual_properties_aspect(cx_network, node_properties)

style_network = ndex2.create_nice_cx_from_file("./WP4571.cx.json")
cx_network.apply_style_from_network(style_network)

set_cartesian_layout_aspect(cx_network, cartesianLayout)

cx_network.print_summary()

mycx = cx_network.to_cx()
# print(mycx)
pprint.pprint(mycx, depth=4)

# result = cx_network.upload_to(
#    server="http://test.ndexbio.org", username=NDEX_USER, password=NDEX_PWD
# )

result = cx_network.update_to(
    server="http://test.ndexbio.org",
    username=NDEX_USER,
    password=NDEX_PWD,
    uuid="99698d91-9155-11e9-b7e4-0660b7976219",
)

pprint.pprint(result, depth=3)
