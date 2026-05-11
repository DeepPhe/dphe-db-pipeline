
def visualize_cancer_counts_by_demographics(conn, output_file=None):
    """
    Create visualizations showing percentages of cancer by gender, age decile, and race.

    Parameters:
    -----------
    conn : database connection object
        Connection to the database containing the tables
    output_file : str, optional
        Path to save the output visualization. If None, display the plot.

    Returns:
    --------
    DataFrame with the count and percentage statistics
    """
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np

    # Query to get cancer data with demographics
    query = """
    SELECT
        D.CANCER,
        P.GENDER,
        P.RACE,
        D.age_at_dx,
        COUNT(*) as count
    FROM
        CALCULATED_DX_DATA D
    JOIN
        CALCULATED_PATIENT_DATA P ON D.PERSON_ID = P.PERSON_ID
    WHERE
        D.CANCER IS NOT NULL
        AND P.GENDER IS NOT NULL
        AND D.age_at_dx IS NOT NULL
    GROUP BY
        D.CANCER, P.GENDER, P.RACE, D.age_at_dx
    ORDER BY
        D.CANCER, P.GENDER, P.RACE, D.age_at_dx
    """

    # Load data into pandas DataFrame
    df = pd.read_sql(query, conn)

    # Create age deciles
    df['age_decile'] = pd.cut(
        df['age_at_dx'],
        bins=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 120],
        labels=['0-9', '10-19', '20-29', '30-39', '40-49', '50-59', '60-69', '70-79', '80-89', '90+']
    )

    # Aggregate counts by cancer, gender, race, and age decile
    agg_df = df.groupby(['CANCER', 'GENDER', 'RACE', 'age_decile'])['count'].sum().reset_index()

    # Set up figure with three subplots
    fig, axes = plt.subplots(3, 1, figsize=(15, 18))

    # 1. Cancer percentages by gender
    gender_counts = agg_df.groupby(['CANCER', 'GENDER'])['count'].sum().reset_index()

    # Calculate total counts per cancer type for percentage calculation
    cancer_totals = gender_counts.groupby('CANCER')['count'].sum().reset_index()
    cancer_totals.rename(columns={'count': 'total'}, inplace=True)

    # Merge totals back to get percentages
    gender_counts = pd.merge(gender_counts, cancer_totals, on='CANCER')
    gender_counts['percentage'] = (gender_counts['count'] / gender_counts['total']) * 100

    # Create pivot table with percentages
    gender_pivot = gender_counts.pivot(index='CANCER', columns='GENDER', values='percentage').fillna(0)

    gender_pivot.plot(kind='bar', stacked=True, ax=axes[0])
    axes[0].set_title('Cancer Distribution by Gender (Percentage)', fontsize=14)
    axes[0].set_xlabel('Cancer Type')
    axes[0].set_ylabel('Percentage (%)')
    axes[0].legend(title='Gender')
    axes[0].set_ylim(0, 100)

    # 2. Cancer percentages by age decile
    age_counts = agg_df.groupby(['CANCER', 'age_decile'])['count'].sum().reset_index()

    # Calculate totals and percentages
    age_counts = pd.merge(age_counts, cancer_totals, on='CANCER')
    age_counts['percentage'] = (age_counts['count'] / age_counts['total']) * 100

    age_pivot = age_counts.pivot(index='CANCER', columns='age_decile', values='percentage').fillna(0)

    # Ensure age deciles are in correct order
    if not age_pivot.empty:
        cols_order = ['0-9', '10-19', '20-29', '30-39', '40-49', '50-59',
                      '60-69', '70-79', '80-89', '90+']
        age_pivot = age_pivot.reindex(columns=cols_order, fill_value=0)

    age_pivot.plot(kind='bar', stacked=True, ax=axes[1])
    axes[1].set_title('Cancer Distribution by Age Decile (Percentage)', fontsize=14)
    axes[1].set_xlabel('Cancer Type')
    axes[1].set_ylabel('Percentage (%)')
    axes[1].legend(title='Age Group')
    axes[1].set_ylim(0, 100)

    # 3. Cancer percentages by race
    race_counts = agg_df.groupby(['CANCER', 'RACE'])['count'].sum().reset_index()

    # Calculate totals and percentages
    race_counts = pd.merge(race_counts, cancer_totals, on='CANCER')
    race_counts['percentage'] = (race_counts['count'] / race_counts['total']) * 100

    race_pivot = race_counts.pivot(index='CANCER', columns='RACE', values='percentage').fillna(0)

    race_pivot.plot(kind='bar', stacked=True, ax=axes[2])
    axes[2].set_title('Cancer Distribution by Race (Percentage)', fontsize=14)
    axes[2].set_xlabel('Cancer Type')
    axes[2].set_ylabel('Percentage (%)')
    axes[2].legend(title='Race')
    axes[2].set_ylim(0, 100)

    plt.tight_layout()

    # Save or display the visualization
    if output_file:
        plt.savefig(output_file)
    else:
        plt.show()

    # Calculate summary statistics
    gender_summary = agg_df.groupby('GENDER')['count'].sum()
    age_summary = agg_df.groupby('age_decile')['count'].sum()
    race_summary = agg_df.groupby('RACE')['count'].sum()

    # Add percentage breakdowns
    gender_pct = (gender_summary / gender_summary.sum()) * 100
    age_pct = (age_summary / age_summary.sum()) * 100
    race_pct = (race_summary / race_summary.sum()) * 100

    return {
        'by_gender_age_race': agg_df,
        'gender_summary': gender_summary,
        'age_summary': age_summary,
        'race_summary': race_summary,
        'gender_percentage': gender_pct,
        'age_percentage': age_pct,
        'race_percentage': race_pct
    }
def visualize_age_distribution_by_demographic_and_cancer(conn, demographic='GENDER', output_file=None):
    """
    Create visualizations showing the distribution of AGE_AT_DX by demographic (gender, race, or ethnicity)
    for each cancer type using distribution graphs.

    Parameters:
    -----------
    conn : database connection object
        Connection to the database containing tables
    demographic : str, optional
        Demographic variable to visualize by: 'GENDER', 'RACE', or 'ETHNICITY' (default: 'GENDER')
    output_file : str, optional
        Path to save the output visualization. If None, display the plot

    Returns:
    --------
    DataFrame with the distribution statistics
    """
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np

    # Validate demographic parameter
    valid_demographics = ['GENDER', 'RACE', 'ETHNICITY']
    if demographic not in valid_demographics:
        raise ValueError(f"Invalid demographic parameter. Choose from: {', '.join(valid_demographics)}")

    # Query to get age at diagnosis, cancer type, and demographic
    query = f"""
    SELECT
        D.CANCER,
        D.age_at_dx,
        P.{demographic},
        COUNT(*) as count
    FROM
        CALCULATED_DX_DATA D
    JOIN
        CALCULATED_PATIENT_DATA P ON D.PERSON_ID = P.PERSON_ID
    WHERE
        D.age_at_dx IS NOT NULL
        AND D.CANCER IS NOT NULL
        AND P.{demographic} IS NOT NULL
    GROUP BY
        D.CANCER, D.age_at_dx, P.{demographic}
    ORDER BY
        D.CANCER, P.{demographic}, D.age_at_dx
    """

    # Load data into pandas DataFrame
    df = pd.read_sql(query, conn)

    # Expand the data based on count column
    expanded_df = pd.DataFrame({
        'CANCER': df['CANCER'].repeat(df['count']),
        'age_at_dx': df.apply(lambda x: [x['age_at_dx']] * x['count'], axis=1).explode(),
        demographic: df[demographic].repeat(df['count'])
    })

    # Get unique cancer types
    cancer_types = expanded_df['CANCER'].unique()

    # Create subplots for each cancer type
    n_cancers = len(cancer_types)
    n_cols = min(3, n_cancers)
    n_rows = (n_cancers + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4*n_rows))
    axes = np.array(axes).flatten()

    # Plot KDE for each cancer type with demographic differentiation
    for i, cancer in enumerate(cancer_types):
        cancer_data = expanded_df[expanded_df['CANCER'] == cancer]

        # Limit to top 5 categories if more than 5 exist
        if len(cancer_data[demographic].unique()) > 5:
            top_categories = cancer_data[demographic].value_counts().nlargest(5).index
            plot_data = cancer_data[cancer_data[demographic].isin(top_categories)]
            axes[i].set_title(f'{cancer} (Top 5 {demographic.lower()})')
        else:
            plot_data = cancer_data
            axes[i].set_title(f'{cancer}')

        sns.kdeplot(
            data=plot_data,
            x='age_at_dx',
            hue=demographic,
            fill=True,
            alpha=0.5,
            ax=axes[i]
        )
        axes[i].set_xlabel('Age at Diagnosis')
        axes[i].set_ylabel('Density')

    # Hide unused subplots
    for j in range(i+1, len(axes)):
        axes[j].set_visible(False)

    plt.suptitle(f'Age Distribution at Diagnosis by Cancer Type and {demographic.capitalize()}', fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    # Save or display the visualization
    if output_file:
        plt.savefig(output_file)
    else:
        plt.show()

    # Calculate summary statistics
    summary = expanded_df.groupby(['CANCER', demographic])['age_at_dx'].describe()

    return summary

def visualize_age_distribution_by_cancer(conn, output_file=None):
    """
    Create visualizations showing the distribution of AGE_AT_DX per cancer type
    using distribution graphs instead of boxplots/violin plots.
    """
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns

    # Query to get age at diagnosis and cancer type
    query = """
    SELECT 
        CANCER, 
        age_at_dx,
        COUNT(*) as count
    FROM 
        CALCULATED_DX_DATA
    WHERE
        age_at_dx IS NOT NULL
        AND CANCER IS NOT NULL
    GROUP BY 
        CANCER, age_at_dx
    ORDER BY 
        CANCER, age_at_dx
    """

    # Load data into pandas DataFrame
    df = pd.read_sql(query, conn)

    # Expand the data based on count column
    expanded_df = pd.DataFrame({
        'CANCER': df['CANCER'].repeat(df['count']),
        'age_at_dx': df.apply(lambda x: [x['age_at_dx']] * x['count'], axis=1).explode()
    })

    # Create a figure
    plt.figure(figsize=(12, 8))

    # Create a KDE plot for all cancer types
    sns.kdeplot(
        data=expanded_df,
        x='age_at_dx',
        hue='CANCER',
        fill=True,
        alpha=0.4,
        common_norm=False
    )

    plt.title('Age Distribution at Diagnosis by Cancer Type', fontsize=14)
    plt.xlabel('Age at Diagnosis')
    plt.ylabel('Density')
    plt.legend(title='Cancer Type', bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()

    # Save or display the visualization
    if output_file:
        plt.savefig(output_file)
    else:
        plt.show()

    # Calculate summary statistics
    summary = expanded_df.groupby('CANCER')['age_at_dx'].describe()

    return summary