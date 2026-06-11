from ..db.omop.icd_ops import process_icd_operation, update_calculated_dx_data
from ..db.omop.lookup_table_ops import create_lookup_tables
from ..db.utils.column_ops import (
    add_column,
    change_column_type,
    create_table_for_column,
    get_column_type,
    insert_single_column_from_muitlple_columns,
    update_column_with_join,
    update_single_column,
)
from ..db.utils.csv_ops import process_a_csv_file
from ..db.utils.indexing_ops import add_index, loop_indexes
from ..db.utils.query_utils import execute_query


def process_csv_file(cursor, conn, csv_path, batch_size=5000):
    process_a_csv_file(cursor, conn, csv_path, batch_size=batch_size)


def change_column_types(cursors, conns, config):
    """
    Process the configuration and change column types as specified.
    """
    if 'change_column_types' not in config.get('before_update'):
        print("No column type changes defined in configuration.")
        return

    for column_change in config['before_update']['change_column_types']:
        schema_name = column_change.get('destination_schema', None)
        table_name = column_change['destination_table']
        column_name = column_change['destination_column']
        new_type = column_change['destination_column_type']

        current_type = get_column_type(cursors[schema_name], conns[schema_name], table_name, column_name)
        if current_type is None:
            print(f"Column {column_name} does not exist in table {table_name}. Skipping type change.")
        elif current_type.lower() != new_type.lower():
            print(
                f"Changing column type for {schema_name}.{table_name}.{column_name} from {current_type} to {new_type}")
            change_column_type(cursors[schema_name], conns[schema_name], table_name, column_name, new_type,
                               commit=True)
        else:
            print(f"Column {column_name} already has type {current_type}. No change needed.")


def add_indexes_before_update(cursors, conns, config):
    loop_indexes(cursors, config, conns, before=True)


def add_lookup_tables(cursors, conns, config):
    """
    Add lookup tables as defined in the configuration.
    """
    for lookup in config['after_update']['lookup_tables']:
        destination_schema = lookup.get('destination_schema', None)
        cursor = cursors[destination_schema]
        conn = conns[destination_schema]
        create_lookup_tables(cursor, conn, config)


def add_indexes_after_update(cursors, conns, config):
    loop_indexes(cursors, config, conns, before=False)


def create_columns(cursors, conns, config):
    """
    Process all column updates as defined in the configuration.
    """
    for column in config['after_update']['create_columns']:
        destination_schema = column.get('destination_schema', None)
        if destination_schema is None:
            destination_schema = column['operation']['destination_schema']
        destination_table = column.get('destination_table', None)
        destination_column = column.get('destination_column', None)
        destination_column_type = column.get('destination_column_type', None)
        destination_column_default = column.get('destination_column_default', None)
        destination_column_nullable = column.get('destination_column_nullable', None)
        source_table = column.get('source_table', None)
        source_columns = column.get('source_columns', None)
        source_tables = column.get('source_tables', None)
        join_on = column.get('join_on', None)
        verb = column.get('verb', None)
        index = column.get('index', None)
        if index is None:
            index = column.get('destination_column_index', 'NO')
        key_length = column.get('key_length', None)
        operation = column.get('operation', None)

        source_schema = column.get('source_schema', None)

        cursor = cursors[destination_schema]
        conn = conns[destination_schema]

        if source_columns is not None:
            source_columns = source_columns.split(",")

        if source_tables is not None:
            source_tables = source_tables.split(",")

        if destination_table is not None:
            create_table_for_column(cursor, conn, destination_table, destination_schema, commit=True)

            # Add the column if it doesn't exist
            add_column(cursor, conn, destination_table, destination_column, destination_column_type,
                       destination_column_default,
                       destination_column_nullable, commit=True)

        # Update the column with data from the source table
        if source_columns is not None:
            if len(source_columns) > 1:
                if verb == "UPDATE":
                    update_column_with_join(cursor, conn, destination_table, destination_column, source_schema,
                                            source_tables,
                                            source_columns,
                                            join_on, commit=True)
                else:
                    if verb == "INSERT":
                        insert_single_column_from_muitlple_columns(cursor, conn, destination_table, destination_column,
                                                                   destination_column_type,
                                                                   source_schema, source_columns, source_tables,
                                                                   join_on, commit=True)
                    elif verb == "UPDATE":
                        update_single_column(cursor, conn, destination_table, destination_column,
                                             destination_column_type,
                                             source_schema, source_columns[0], source_table,
                                             join_on, commit=True)
        else:
            if operation is not None:
                process_operation(cursor, conn, operation)

        if index == "YES":
            if key_length is None:
                key_length = 255
            add_index(cursor, conn, destination_table, destination_column, key_length, commit=True)


def process_operation(cursor, conn, config):
    # if config["operation"]["type"] == 'AGE_AT':
    #     process_age_at_operation(cursor, conn, config)
    # if config["operation"]["type"] == 'ICD10':
    #     #process_icd10_operation(cursor, conn, config["operation"])
    #     # create_icd_lookup_table(cursor, conn, icd10=True)

    # if config["operation"]["type"] == 'ICD9':
    #     # create_icd_lookup_table(cursor, conn, icd9=True)
    #     process_icd9_operation(cursor, conn, config["operation"])
    process_icd_operation(cursor, conn, config)
    update_calculated_dx_data(cursor, conn)


def process_age_at_operation(cursor, conn, config):
    """
    Process an AGE_AT operation from the config and generate/execute the appropriate SQL.

    This creates a query to calculate age difference between a birth date and
    the earliest/latest condition date from multiple potential sources.
    """
    destination_table = config['destination_table']
    destination_column = config['destination_column']
    join_on = config['join_on']
    operation = config['operation']

    # Get birth date information
    birth_column = operation['birth_column']
    birth_column_type = operation.get('birth_column_type', 'TEXT')
    rule = operation['rule']  # USE_EARLIEST or USE_LATEST
    age_at_columns = operation['age_at_columns']

    # Build the SQL components
    joins = []
    condition_dates = []
    where_clauses = []

    # Create table aliases to avoid name conflicts
    for i, col_config in enumerate(age_at_columns):
        table = col_config['table']
        alias = f"t{i}"
        column = col_config['column']
        datatype = col_config.get('datatype', 'DATE')

        # Build the join clause
        join_clause = f"JOIN {table} {alias} ON d.{join_on} = {alias}.{join_on}"
        joins.append(join_clause)

        # Add the condition date (with CAST if needed)
        cast_column = f"CAST({alias}.{column} AS DATE)" if datatype != 'DATE' else f"{alias}.{column}"
        condition_dates.append(cast_column)

        # Add any restrictions to the where clause
        if 'restrictions' in col_config:
            if 'has_values' in col_config['restrictions']:
                # Handle the case with a list of values
                column_name = col_config['restrictions']['column']
                values_list = col_config['restrictions']['has_values']
                values_str = ', '.join(str(v) for v in values_list)
                where_clauses.append(f"{alias}.{column_name} IN ({values_str})")
            else:
                # Handle the simple key-value pair case
                for field, value in col_config['restrictions'].items():
                    where_clauses.append(f"{alias}.{field} = '{value}'")

    # Combine the condition dates with LEAST or GREATEST based on the rule
    date_function = "LEAST" if rule == "USE_EARLIEST" else "GREATEST"
    combined_dates = f"{date_function}({', '.join(condition_dates)})"

    # Build the complete query
    if birth_column_type != 'DATE':
        birth_date = f"CAST(d.{birth_column} AS DATE)"
    else:
        birth_date = f"d.{birth_column}"

    query = f"""
    UPDATE {destination_table} d
    {' '.join(joins)}
    SET d.{destination_column} = TIMESTAMPDIFF(
        YEAR,
        {birth_date},
        {combined_dates}
    )
    {'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''};
    """

    print(f"Executing AGE_AT operation for {destination_column}...")
    execute_query(cursor, conn, query, commit=True)
