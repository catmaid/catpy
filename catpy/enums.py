from enum import Enum


class ConnectorRelationType(Enum):
    SYNAPTIC = "Synaptic"
    GAP_JUNCTION = "Gap junction"
    TIGHT_JUNCTION = "Tight junction"
    DESMOSOME = "Desmosome"
    ABUTTING = "Abutting"
    ATTACHMENT = "Attachment"
    SPATIAL = "Spatial"
    OTHER = ""

    @classmethod
    def from_relation(cls, relation):
        return {
            ConnectorRelation.presynaptic_to: cls.SYNAPTIC,
            ConnectorRelation.postsynaptic_to: cls.SYNAPTIC,
            ConnectorRelation.gapjunction_with: cls.GAP_JUNCTION,
            ConnectorRelation.tightjunction_with: cls.TIGHT_JUNCTION,
            ConnectorRelation.desmosome_with: cls.DESMOSOME,
            ConnectorRelation.abutting: cls.ABUTTING,
            ConnectorRelation.attached_to: cls.ATTACHMENT,
            ConnectorRelation.close_to: cls.SPATIAL,
            ConnectorRelation.other: cls.OTHER,
        }[relation]


class ConnectorRelation(Enum):
    """Enum describing the link between a treenode and connector, i.e. the treenode is ____ to the connector.

    The enum's ``name`` is CATMAID's concept of "relation name":
    what is returned in the ``relation`` field of the <pid>/connectors/types/ response.

    The enum's ``value`` is the ``name`` field of the <pid>/connectors/types/ response.

    The mappings from relation name to relation ID are project-specific and must be fetched from CATMAID.
    """

    other = ""
    presynaptic_to = "Presynaptic"
    postsynaptic_to = "Postsynaptic"
    gapjunction_with = "Gap junction"
    tightjunction_with = "Tight junction"
    desmosome_with = "Desmosome"
    abutting = "Abutting"
    attached_to = "Attachment"
    close_to = "Close to"

    @property
    def type(self):
        return ConnectorRelationType.from_relation(self)

    @property
    def is_synaptic(self):
        return self.type == ConnectorRelationType.SYNAPTIC

    def __str__(self):
        return self.value
