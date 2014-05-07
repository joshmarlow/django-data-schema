from datetime import datetime, date

from django.contrib.contenttypes.models import ContentType
from django.db import models
from manager_utils import ManagerUtilsManager

from data_schema.convert_value import convert_value


class DataSchemaManager(ManagerUtilsManager):
    """
    A model manager for data schemas. Caches related attributes of data schemas.
    """
    def get_queryset(self):
        return super(DataSchemaManager, self).get_queryset().select_related(
            'model_content_type').prefetch_related('fieldschema_set')


class DataSchema(models.Model):
    """
    A configuration for a metric record that is tracked by animal. Specifies the main options and
    allows MetricRecordFieldConfigs to be attached to it, which specify the schema of the metric
    record. Also defines a unique name for the metric record and a display name.
    """
    # The content type of the django model for which this schema is related. If None, this schema is
    # for a dictionary of data.
    model_content_type = models.ForeignKey(ContentType, null=True, default=None)

    # A custom model manager that caches objects
    objects = DataSchemaManager()

    def get_unique_fields(self):
        """
        Gets all of the fields that create the uniqueness constraint for a metric record.
        """
        if not hasattr(self, '_unique_fields'):
            # Instead of querying the reverse relationship directly, assume that it has been cached
            # with prefetch_related and go through all fields.
            setattr(self, '_unique_fields', [
                field for field in self.fieldschema_set.all() if field.uniqueness_order is not None
            ])
            self._unique_fields.sort(key=lambda k: k.uniqueness_order)
        return self._unique_fields

    def get_fields(self):
        """
        Gets all fields in the schema. Note - dont use django's order_by since we are caching the fieldschema_set
        beforehand.
        """
        return sorted(self.fieldschema_set.all(), key=lambda k: k.field_position)


class FieldSchemaType(object):
    """
    Specifies all of the field schema types supported.
    """
    DATE = 'DATE'
    DATETIME = 'DATETIME'
    INT = 'INT'
    FLOAT = 'FLOAT'
    STRING = 'STRING'


# Create a mapping of the field schema types to their associated python types
FIELD_SCHEMA_PYTHON_TYPES = {
    FieldSchemaType.DATE: date,
    FieldSchemaType.DATETIME: datetime,
    FieldSchemaType.INT: int,
    FieldSchemaType.FLOAT: float,
    FieldSchemaType.STRING: str,
}


class FieldSchema(models.Model):
    """
    Specifies the schema for a field in a piece of data.
    """
    class Meta:
        unique_together = ('data_schema', 'field_key')

    # The data schema to which this field belongs
    data_schema = models.ForeignKey(DataSchema)

    # The key for the field in the data
    field_key = models.CharField(max_length=64)

    # The order in which this field appears in the UID for the record. It is null if it does
    # not appear in the uniqueness constraint
    uniqueness_order = models.IntegerField(null=True)

    # The position of the field. This ordering is relevant when parsing a list of fields into
    # a dictionary with the field names as keys
    field_position = models.IntegerField(null=True)

    # The type of field. The available choices are present in the FieldSchemaType class
    field_type = models.CharField(
        max_length=32, choices=((field_type, field_type) for field_type in FieldSchemaType.__dict__))

    # If the field is a string and needs to be converted to another type, this string specifies
    # the format for a field
    field_format = models.CharField(null=True, blank=True, default=None, max_length=64)

    # Use django manager utils to manage FieldSchema objects
    objects = ManagerUtilsManager()

    def set_value(self, obj, value):
        """
        Given an object, set the value of the field in that object.
        """
        if isinstance(obj, list):
            obj[self.field_position] = value
        elif isinstance(obj, dict):
            obj[self.field_key] = value
        else:
            setattr(obj, self.field_key, value)

    def get_value(self, obj):
        """
        Given an object, return the value of the field in that object.
        """
        if isinstance(obj, list):
            value = obj[self.field_position]
        elif isinstance(obj, dict):
            value = obj[self.field_key]
        else:
            value = getattr(obj, self.field_key)

        return convert_value(FIELD_SCHEMA_PYTHON_TYPES[self.field_type], value, self.field_format)
