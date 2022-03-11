from config import settings
import neo4j
import json
import logging

#Logger
LOGGER = logging.getLogger(__name__)

# Configuration for Node Labels to be used
_NODE_TYPES = settings.get(
    "graphdb.node_types", ["ENTERPRISE", "FACILITY", "AREA", "LINE", "DEVICE"])

# Configuration on which attributes in the message need not be persisted
_IGNORED_ATTRIBUTES = settings.get("graphdb.ignored_attributes", [])


class GraphDBHandler:

    def __init__(self, uri: str, user: str, password: str):
        ## TODO support other authentications like cert based authentication
        try:
            self.driver = neo4j.GraphDatabase.driver(uri,
                                                     auth=(user, password))
        except Exception as ex:
            LOGGER.error("Failed to create the driver:", ex)

    def close(self):
        if self.driver is not None:
            try:
                self.driver.close()
            except Exception as ex:
                LOGGER.error("Failed to close the driver:", ex)

    def persistMQTTmsg(self,
                       topic: str,
                       message: str,
                       database: str = neo4j.DEFAULT_DATABASE):
        """
        Persists all nodes and the message as attributes to the leaf node
        ----------
        topic: str
            The topic on which the message was sent
        message: str 
            The MQTT message. String is expected to be JSON formatted
        database : str = neo4j.DEFAULT_DATABASE
            The Neo4j database in which this data should be persisted    
        """
        if [ database is None ] :
            database = ""
        response = None
        with self.driver.session(database=f"{database}") as session:
            response = session.write_transaction(self.save_all_nodes, topic,
                                                 message)
        return response

    @staticmethod
    def save_all_nodes(session, topic: str, message: str):
        """
        Iterate the topics by '/'. create node for each level and merge the messages to the final node
        For the other topics in the hierarchy a node will be created / merged and linked to the parent topic node
        Parameters
        ----------
        session : 
            The Neo4j database session used for the write transaction 
        topic: str
            The topic on which the message was sent
        message: str 
            The MQTT message. String is expected to be JSON formatted 
        """
        response = None
        count = 0
        lastnode = None
        nodes = topic.split('/')
        for node in nodes:
            # TODO improve logger message
            LOGGER.debug(node)

            jsonStr = None
            if (count == len(nodes)):
                ## Save the message only for the leaf node
                jsonStr = message

            if (count < len(_NODE_TYPES)):
                response = GraphDBHandler._saveNode(session, node,
                                                    _NODE_TYPES[count],
                                                    jsonStr)
            else:
                response = GraphDBHandler._saveNode(
                    session, node,
                    f"{_NODE_TYPES[len(_NODE_TYPES)]}_depth_{ count - len(_NODE_TYPES)+ 1}",
                    jsonStr, lastnode)
            count += 1
            lastnode = node
        return response

    @staticmethod
    def _saveNode(session: neo4j.Session,
                  nodename: str,
                  nodetype: str,
                  message=None,
                  parent: str = None):
        """
        Creates or Merges the MQTT message as a Graph node. Each level of the topic is also persisted 
        as a graph node with appropriate parent relationship
        Parameters
        ----------
        session  : neo4j.Session
            Neo4j session object
        nodename : str
            Trimmed name of the topic
        nodetype : str
            Based on ISA-95 part 2 the nested depth of the topic determines the node type. 
            Also see settings.yaml graphdb.node_types
        message : str
            The JSON string delivered as message in the MQTT payload. Defaults to None (for all intermettent topics)
        parent  : str
            The name of the parent node to which a relationship will be established. Defaults to None(for root nodes)     
        """
        attributes = r'{ }'
        LOGGER.debug(
            f"Saving node:{nodename} of type:{nodetype} and message:{message} with parent:{parent}"
        )

        ## Neo4j supports only flat messages. also the json.load does not remove quotes around the keys of the dict
        ## Also need to ensure that the message doesn't contain any attribute with the name "node_name"
        if (message is not None):
            attributes = GraphDBHandler._flatten_json_for_Neo4J(
                json.loads(message))

        if (parent is not None):
            LOGGER.debug(f"\"{nodename}\" is a child node of \"{parent}\"")
            node = session.run(
                "MATCH (parent { node_name: $parent})"
                "MERGE (node: $nodetype { node_name: $nodename }) "
                "ON CREATE"
                "     SET node._created = timestamp()"
                "ON MATCH"
                "     SET node._modified = timestamp()"
                "SET node += $attributes"
                "MERGE (parent) -[r:PARENT_OF]-> (node)"
                "RETURN node",
                parent=parent,
                nodename=nodename,
                nodetype=nodetype,
                attributes=attributes)
        else:
            LOGGER.debug(f"\"{nodename}\" is a root node")
            ## Create the node with no parent relationship
            node = session.run(
                "MERGE (node: $nodetype { node_name: $nodename }) "
                "ON CREATE "
                "     SET node._created = timestamp() "
                "ON MATCH"
                "     SET node._modified = timestamp() "
                "SET node += $attributes "
                "RETURN node ",
                nodetype=nodetype,
                nodename=nodename,
                attributes=attributes)
        return node

    @staticmethod
    def _flatten_json_for_Neo4J(mqtt_msg: dict) -> str:
        """
        Utility methos to convert a nested JSON into a flat structure
        Keys for lists will be of the form <key>_<count>
        Keys for dicts will be of the form <parent key>_<child key>
        if any attribute is named "node_name" it will be replaced by "NODE_NAME"
        if any attribute is on the ignore list the attribute and the value will not be persisted
        Parameters
        ----------
        message  : dict
           created by coverting MQTT message string in JSON format to python object
        """
        LOGGER.debug(mqtt_msg)
        output = {}

        def flatten(json_object, name=''):
            if (type(json_object) is dict):
                for items in json_object:
                    flatten(json_object[items], name + items + '_')
            elif (type(json_object) is list):
                i = 0
                for items in json_object:
                    flatten(items, name + str(i) + '_')
                    i += 1
            else:
                if (name[:-1] == "node_name"):
                    name = name.upper()
                output[name[:-1]] = json_object

        flatten(mqtt_msg)
        string_output = "{"
        for key, value in output.items():
            LOGGER.debug(key, value)
            if (key in _IGNORED_ATTRIBUTES):
                LOGGER.INFO(
                    f"Skipping to persist value for key: {key}, as it is on the ignore list"
                )
            else:
                string_output += f" {key} : \"{value}\" ,"
        string_output = string_output[:-1] + " }"
        return string_output
