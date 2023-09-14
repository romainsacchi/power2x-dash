import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import gunicorn                     #whilst your local machine's webserver doesn't need this, Heroku's linux webserver (i.e. dyno) does. I.e. This is your HTTP server
from whitenoise import WhiteNoise


# Function to remove common string items from x-axis labels
def remove_common_items(labels):
    words_list = [label.split(' | ') for label in labels]
    if len(words_list) < 2:  # No intersection possible if fewer than 2 sets
        return labels
    
    common_words = set(words_list[0]).intersection(*words_list[1:])
    
    cleaned_labels = []
    for label in labels:
        cleaned_label = ' | '.join([word for word in label.split(' | ') if word not in common_words]).strip(' | ')
        cleaned_labels.append(cleaned_label)
    
    cleaned_labels = [c.replace("|   |", "|") for c in cleaned_labels]
    cleaned_labels = [c.replace("Yes | ", "") for c in cleaned_labels]
    cleaned_labels = [c.replace("No | ", "") for c in cleaned_labels]
    
    return cleaned_labels

# Load the data
file_path = 'all_results.xlsx'
gwp_data = pd.read_excel(file_path, sheet_name='all results')

gwp_data = gwp_data.loc[~gwp_data["product"].isnull()]

# Define filter and contributor columns (excluding 'main?')
filter_columns = [
    "impact category", "main?", "product", "energy carrier", "end-use", "end-use technology",
    "transport type", "synthesis type", "electrolyzer tech", "feedstock origin",
    "CO2 origin", "CO2 allocation"
]
contributor_columns = [
    "boiler", "CCS/CCU", "CHP", "CNG pipeline", "electricity", "electrolyzer",
    "emissions", "EoL", "fuel cell", "hydrogen pipeline", "hydrogen production",
    "hydrogen storage", "hydrogen supply", "leak", "methanol production",
    "methanol supply", "others", "SNG production", "SNG supply", "steam",
    "transport", "water"
]

# Initialize Dash app
app = dash.Dash(__name__)

# Reference the underlying flask app (Used by gunicorn webserver in Heroku production deployment)
server = app.server

# Enable Whitenoise for serving static files from Heroku (the /static folder is seen as root by Heroku)
#server.wsgi_app = WhiteNoise(server.wsgi_app, root='static/')

# Function to generate dropdown options
def generate_dropdown_options(data, column):
    options = sorted([str(opt) for opt in data[column].unique() if opt == opt])  # Convert to string and filter out NaN
    return [{'label': opt, 'value': opt} for opt in options]

# App layout
app.layout = html.Div([
    html.H1("Analysis"),
    html.Div([
        html.Div([
            html.Label(filter_col),
            dcc.Dropdown(
                id=f'dropdown-{filter_col}',
                options=generate_dropdown_options(gwp_data, filter_col),
                multi=True
            )
        ], style={'width': '48%', 'display': 'inline-block'}) for filter_col in filter_columns
    ]),
    dcc.Graph(id='stacked-bar', style={'height': '80vh'})  # Fixed height
])

# Callback for dynamically updating dropdown options
@app.callback(
    [Output(f'dropdown-{filter_col}', 'options') for filter_col in filter_columns],
    [Input(f'dropdown-{filter_col}', 'value') for filter_col in filter_columns],
    prevent_initial_call=True
)
def update_dropdown_options(*filter_values):
    filtered_data = gwp_data.copy()
    
    # Apply filters from all dropdowns
    for col, values in zip(filter_columns, filter_values):
        if values:
            filtered_data = filtered_data[filtered_data[col].isin(values)]
    
    # Generate new options for each dropdown based on filtered data
    new_options = [generate_dropdown_options(filtered_data, col) for col in filter_columns]
    return new_options

# Callback for updating graph
@app.callback(
    Output('stacked-bar', 'figure'),
    [Input(f'dropdown-{filter_col}', 'value') for filter_col in filter_columns]
)
def update_graph(*filter_values):
    filtered_data = gwp_data.copy()
    
    # Apply filters
    for col, value in zip(filter_columns, filter_values):
        if value:
            filtered_data = filtered_data[filtered_data[col].isin(value)]
    
    # Remove non-contributing categories based on sum
    contributing_columns = [col for col in contributor_columns if filtered_data[col].sum() > 0]
    
    # Create x-axis labels based on filter columns
    filtered_data['x_axis_label'] = filtered_data[filter_columns].apply(
        lambda row: ' | '.join([str(v) for v in row if v == v]), axis=1
    )
    
    # Remove common string items from x-axis labels
    cleaned_labels = remove_common_items(filtered_data['x_axis_label'].to_list())
    filtered_data['x_axis_label'] = cleaned_labels

    filtered_data = filtered_data.sort_values('x_axis_label')

    # Determine the title based on selected "product"
    product_value = filter_values[filter_columns.index("product")]  # Assuming 'product' is in your filter_columns
    if product_value is None:
        title = 'Contributions'
    elif 'heat' in product_value:
        title = 'per MJ heat'
    elif 'electricity' in product_value:
        title = 'per kWh electricity'
    else:
        title = f'per kg of {", ".join(product_value)}'

    
    # Generate stacked bar chart
    fig = px.bar(filtered_data, x='x_axis_label', y=contributing_columns, title=title)
    
    # Update layout to maintain figure's height and rotate x-axis labels
    fig.update_layout(
        barmode='stack',
        xaxis=dict(tickangle=45, title=None),  # Remove x-axis title
        yaxis=dict(title=list(filtered_data["unit"].unique())[0]),
        margin=dict(t=60, b=160)  # Increase bottom margin to accommodate rotated labels
    )
    
    return fig

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
