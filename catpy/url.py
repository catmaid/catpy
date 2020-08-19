import webbrowser
from warnings import warn


def get_typed(d, key, constructor=None, default=None):
    """
    like dict.get, but if the response/default is not None, pass it to the given constructor.

    Parameters
    ----------
    d : dict
    key : hashable
    constructor : callable
    default

    Returns
    -------

    """
    response = d.get(key, default)
    if constructor is None or response is None:
        return response
    else:
        return constructor(response)


class CatmaidUrl(object):
    tracing_tool_name = "tracingtool"

    def __init__(
        self,
        base_url,
        project_id,
        stack_group_id=None,
        stack_id=None,
        scale=0,
        x=None,
        y=None,
        z=None,
        tool=None,
        active_skeleton_id=None,
        active_node_id=None,
    ):
        self.base_url = base_url

        self.project_id = project_id

        self.default_scale = scale

        self.stack_group = None
        self.stack_group_scale = None
        self.stacks = []
        self.set_stack_group(stack_group_id, scale)
        if stack_id is not None:
            self.add_stack(stack_id, scale)

        self.x = x
        self.y = y
        self.z = z

        self.tool = tool
        self.active_skeleton_id = active_skeleton_id
        self.active_node_id = active_node_id

    @classmethod
    def from_catmaid(
        cls,
        catmaid_client,
        stack_group_id=None,
        stack_id=None,
        scale=0,
        x=None,
        y=None,
        z=None,
        tool=None,
        active_skeleton_id=None,
        active_node_id=None,
    ):
        """
        Instantiate CatmaidUrl based on a CATMAID interface instance.

        Parameters
        ----------
        catmaid_client : CatmaidClient or catpy.applications.base.CatmaidClientApplication
        stack_group_id : int
        stack_id : int
        scale : float
        x : float
            x coordinate in project (real) space
        y : float
            y coordinate in project (real) space
        z : float
            z coordinate in project (real) space
        tool : str
        active_skeleton_id : int
        active_node_id : int

        Returns
        -------
        CatmaidUrl
        """
        return cls(
            catmaid_client.base_url,
            catmaid_client.project_id,
            stack_group_id,
            stack_id,
            scale,
            x,
            y,
            z,
            tool,
            active_skeleton_id,
            active_node_id,
        )

    @classmethod
    def from_url(cls, url):
        """
        Instantiate CatmaidUrl based on a URL pulled from a running CATMAID instance.

        Parameters
        ----------
        url : str

        Returns
        -------
        CatmaidUrl
        """
        base_url, args = url.split("/?")
        d = dict(item.split("=") for item in args.split("&"))

        kwargs = dict(
            project_id=get_typed(d, "pid", int),
            scale=None,
            x=get_typed(d, "xp", float),
            y=get_typed(d, "yp", float),
            z=get_typed(d, "zp", float),
            tool=d.get("tool"),
            active_skeleton_id=get_typed(d, "active_skeleton_id", int),
            active_node_id=get_typed(d, "active_node_id", int),
        )

        obj = cls(base_url, **kwargs)
        obj.set_stack_group(stack_group_id=int(d.get("sg")), scale=float(d.get("sgs")))

        stacks = dict()
        scales = dict()
        for key, value in d.items():
            if key.startswith("sid"):
                try:
                    stacks[int(key[3:])] = int(value)
                except ValueError:
                    pass
            elif key.startswith("s"):
                try:
                    scales[int(key[1:])] = int(value)
                except ValueError:
                    pass

        for idx, sid in sorted(stacks.items(), key=lambda x: (x[1], x[0])):
            obj.add_stack(sid, scales.get(idx))

        if obj.default_scale is None:
            obj.default_scale = 0

        return obj

    def add_stack(self, stack_id, scale=None):
        """
        Parameters
        ----------
        stack_id : int
        scale : float

        Returns
        -------
        CatmaidUrl
            A reference to itself, for chaining
        """
        # todo? fetch stack ID from stack name
        self.stacks.append((stack_id, scale))
        if self.default_scale is None:
            self.default_scale = scale
        return self

    def set_stack_group(self, stack_group_id, scale=None):
        """
        Parameters
        ----------
        stack_group_id : int
        scale : float

        Returns
        -------
        CatmaidUrl
            A reference to itself, for chaining
        """
        # todo? fetch stacks from stack group
        self.stack_group = stack_group_id
        self.stack_group_scale = scale
        if self.default_scale is None:
            self.default_scale = scale
        return self

    def _terminate_base_url(self):
        url = self.base_url
        if url.endswith("/"):
            url += "?"
        if not url.endswith("/?"):
            url += "/?"

        return url

    def __str__(self):
        elements = ["pid={}".format(self.project_id)]

        coords = [
            "{}p={}".format(dim, float(getattr(self, dim)))
            for dim in "xyz"
            if getattr(self, dim) is not None
        ]
        if len(coords) == 3:
            elements.extend(coords)
        elif coords:
            warn("Only {} of 3 coordinates found, ignoring".format(len(coords)))

        if self.tool:
            elements.append("tool=" + self.tool)
            if self.tool == "tracingtool":
                elements.append("active_node_id={}".format(self.active_node_id))
                elements.append("active_skeleton_id={}".format(self.active_skeleton_id))

        if self.stack_group is not None:
            elements.append("sg={}".format(self.stack_group))
            elements.append(
                "sgs={}".format(
                    float(self.stack_group_scale)
                    if self.stack_group_scale is not None
                    else float(self.default_scale)
                )
            )

        if not self.stacks:
            warn("No stacks added found, URL may be invalid")
        for idx, (stack_id, scale) in enumerate(self.stacks):
            elements.append("sid{}={}".format(idx, stack_id))
            elements.append(
                "s{}={}".format(
                    idx,
                    float(scale) if scale is not None else float(self.default_scale),
                )
            )

        return self._terminate_base_url() + "&".join(elements)

    def open(self):
        webbrowser.open(str(self), new=2)
