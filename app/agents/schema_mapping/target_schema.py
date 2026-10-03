from pydantic import BaseModel, Field


class TargetField(BaseModel):
    name: str
    data_type: str
    description: str
    allowed_values: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


TARGET_FIELDS = [
    TargetField(
        name="Reference",
        data_type="string",
        description="Unique reference or identifier for the insured location.",
        aliases=[
            "reference",
            "ref",
            "location reference",
            "location id",
            "location number",
            "site reference",
            "site id",
        ],
    ),
    TargetField(
        name="Address",
        data_type="string",
        description="Street address of the insured location.",
        aliases=[
            "address",
            "street address",
            "property address",
            "location address",
            "site address",
        ],
    ),
    TargetField(
        name="City",
        data_type="string",
        description="City or town of the insured location.",
        aliases=[
            "city",
            "town",
            "city name",
            "town name",
        ],
    ),
    TargetField(
        name="State",
        data_type="string",
        description="State or province of the insured location.",
        aliases=[
            "state",
            "state code",
            "state name",
            "province",
            "state/province",
        ],
    ),
    TargetField(
        name="Zip",
        data_type="integer",
        description="ZIP or postal code of the insured location.",
        aliases=[
            "zip",
            "zip code",
            "zipcode",
            "postal code",
            "postal",
        ],
    ),
    TargetField(
        name="County",
        data_type="string",
        description="County of the insured location.",
        aliases=[
            "county",
            "county name",
        ],
    ),
    TargetField(
        name="Country",
        data_type="string",
        description="Country of the insured location.",
        aliases=[
            "country",
            "country name",
            "country code",
        ],
    ),
    TargetField(
        name="Building Value",
        data_type="float",
        description="Replacement or insured value associated with the building.",
        aliases=[
            "building value",
            "building replacement value",
            "building replacement cost",
            "replacement cost",
            "replacement cost new",
            "building cost",
            "bldg value",
            "bldg repl cost new",
            "bldg repl cost",
            "building repl cost",
        ],
    ),
    TargetField(
        name="Contents",
        data_type="float",
        description="Insured value of contents, machinery, equipment, or similar property contents.",
        aliases=[
            "contents",
            "contents value",
            "contents replacement value",
            "contents cost",
            "machinery",
            "equipment",
            "machinery equipment",
            "contents machinery equipment",
        ],
    ),
    TargetField(
        name="BI",
        data_type="float",
        description="Business interruption value.",
        aliases=[
            "bi",
            "business interruption",
            "business income",
            "business income value",
            "bi value",
            "business interruption value",
        ],
    ),
    TargetField(
        name="Occupancy",
        data_type="string",
        description="Primary occupancy or use of the insured location.",
        aliases=[
            "occupancy",
            "occupancy type",
            "property occupancy",
            "building occupancy",
            "use",
            "property use",
        ],
    ),
    TargetField(
        name="Construction",
        data_type="string",
        description="Construction type or construction classification of the building.",
        aliases=[
            "construction",
            "construction type",
            "construction class",
            "building construction",
            "construction code",
        ],
    ),
    TargetField(
        name="Storeys",
        data_type="integer",
        description="Number of storeys or floors in the building.",
        aliases=[
            "storeys",
            "stories",
            "story",
            "storey",
            "number of storeys",
            "number of stories",
            "floors",
            "number of floors",
        ],
    ),
    TargetField(
        name="Number of Buildings",
        data_type="integer",
        description="Number of buildings at the insured location.",
        aliases=[
            "number of buildings",
            "building count",
            "number buildings",
            "no of buildings",
            "no. of buildings",
            "buildings",
            "building number",
        ],
    ),
    TargetField(
        name="Year Built",
        data_type="integer",
        description="Year in which the building was constructed.",
        aliases=[
            "year built",
            "year of construction",
            "construction year",
            "built year",
            "year constructed",
            "built",
        ],
    ),
    TargetField(
        name="Fire Sprinklers (Y/N)",
        data_type="string",
        description="Fire sprinkler protection indicator.",
        allowed_values=[
            "Y",
            "N",
            "Y13",
            "Y(13R)",
        ],
        aliases=[
            "fire sprinklers",
            "fire sprinkler",
            "sprinklers",
            "sprinkler",
            "fire sprinkler protection",
            "sprinkler protection",
            "fire sprinklers y n",
            "fire sprinkler y n",
        ],
    ),
    TargetField(
        name="Other",
        data_type="float",
        description="Other applicable insured value not represented by the specified target fields.",
        aliases=[
            "other",
            "other value",
            "other amount",
            "other property",
            "miscellaneous",
            "misc",
        ],
    ),
]


TARGET_FIELD_NAMES = tuple(field.name for field in TARGET_FIELDS)


TARGET_FIELD_BY_NAME = {
    field.name: field
    for field in TARGET_FIELDS
}