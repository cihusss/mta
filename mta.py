# GA MAT Engine
# Developed by Teo

from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta

import pandas as pd
import datetime
import json
import pygsheets
import numpy as np
import math

#Auth vars
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
KEY_FILE_LOCATION = 'key.json'
# viewID = '59519920'

def initialize_analyticsreporting():
	"""Initializes an Analytics Reporting API V4 service object.act

	Returns:
	An authorized Analytics Reporting API V4 service object.
	"""
	credentials = ServiceAccountCredentials.from_json_keyfile_name(
		KEY_FILE_LOCATION, SCOPES)

	# Build the service object.
	analytics = build('analyticsreporting', 'v4', credentials=credentials)

	return analytics


def get_report(analytics, startDate, endDate, viewID, userID, journeyID):
	"""Queries the Analytics Reporting API V4.

	Args:
		analytics: An authorized Analytics Reporting API V4 service object.
	Returns:
		The Analytics Reporting API V4 response.
	"""
	return analytics.reports().batchGet(
		body={
			'reportRequests': [
			{
			'viewId': viewID,
			'pageSize': 100000,
			'dateRanges': [{'startDate': startDate, 'endDate': endDate}],
			'metrics': [{'expression': 'ga:sessions'}, {'expression': 'ga:timeOnPage'}, {'expression': 'ga:goal1Completions'}],
			'dimensions': [{'name': 'ga:dateHourMinute'}, {'name': f'ga:dimension{userID}'}, {'name': f'ga:dimension{journeyID}'}, {'name': 'ga:medium'}, {'name': 'ga:source'}, {'name': 'ga:deviceCategory'}, {'name': 'ga:campaign'}]
			}]
		}
	).execute()


def generate_output(response, userID, journeyID, sliderVal):
	  
	#Extract Data
	for report in response.get('reports', []):
	  
	    columnHeader = report.get('columnHeader', {})
	    dimensionHeaders = columnHeader.get('dimensions', [])
	    metricHeaders = columnHeader.get('metricHeader', {}).get('metricHeaderEntries', [])
	    rows = report.get('data', {}).get('rows', [])
	    metricHeadersClean = []
	    dimensions = []
	    metrics = []
	    dfdata = []

	    for count, value in enumerate(metricHeaders):
	    	metricHeadersClean.append(metricHeaders[count]['name'])

	    for row in rows:
	    	dimensions.append(row.get('dimensions', []))

	    for count, row in enumerate(rows):
	    	metrics.append(row['metrics'][0]['values'])

	    for count, sublist in enumerate(dimensions):
	    	dfdata.append(sublist)
	    	sublist.extend(metrics[count])

	    columnHeaders = dimensionHeaders + metricHeadersClean

	    # print(dfdata)
	    # print(100*'-')

	    df = pd.DataFrame(dfdata, columns = columnHeaders) 
	 
	#Rename columns
	df.columns = [column.replace(":", "_") for column in df.columns]
	df = df.rename(columns={f'ga_dimension{userID}': 'ga_userId'})
	df = df.rename(columns={f'ga_dimension{journeyID}': 'ga_sessionId'})

	dfConverters = df.copy()
	dfTouchpoints = df.copy()

	# Filter out converters
	dfConverters.query('ga_goal1Completions == "1"', inplace = True)
	converterIDs = dfConverters['ga_userId'].tolist()

	# Filter out all non converter touchpoints 
	dfTouchpoints.query('ga_userId == @converterIDs', inplace = True)
	dfTouchpoints['score'] = 0
	# dfTouchpoints['score'].astype('int32').dtypes
	# dfTouchpoints = dfTouchpoints.reset_index()
	# dfTouchpoints.at[8, 'score'] = 99
	# dfTouchpoints.at[202107310002, 'score'] = 98

	print(f'converters: {len(dfConverters.index)}')
	print(f'touchppoints: {len(dfTouchpoints.index)}')

	print(100*'-')

	# Extract all mediums
	# mediumsAll = list(dict.fromkeys(df['ga_medium'].tolist()))
	mediumsAll = dfTouchpoints.ga_medium.unique().tolist()
	mediumsAll = sorted(mediumsAll)
	
	# Calculate touchpoint count / medium
	dfTPM = dfTouchpoints['ga_medium'].value_counts(dropna = False).rename_axis('mediums').reset_index(name='tps').sort_values('mediums').round(2)
	# Convert to percentages
	dfTPM['tps'] = dfTPM['tps'].div(dfTPM['tps'].sum(axis=0), axis=0) * 100
	dfTPM = dfTPM.round(2)
	print(dfTPM)
	print(100*'-')

	# Calculate weighted touchpoint score / medium using exponential time decay
	today = date.today()
	# Create a df from dfTouchpoints and group it by ga_userId
	dfTouchpointsDecay = dfTouchpoints.groupby('ga_userId')
	# Create dfTouchpointsDecayOutput df with mediumsAll as columns
	dfTouchpointsDecayOutput = pd.DataFrame(columns = mediumsAll)
	# Populate dfTouchpointsDecayOutput with zeros
	for m in mediumsAll:
		dfTouchpointsDecayOutput[m] = [0]

	# Iterate over dfTouchpointsDecay
	for i, group in dfTouchpointsDecay:
		# Print ga_userId
		# print(i)
		# Get last touchpoint date and convert it to date object
		lastTPobj = datetime.datetime.strptime(group.tail(1)['ga_dateHourMinute'].to_string(index = False), '%Y%m%d%H%M')
		# Truncate hours and minutes
		lastTPTrunk = datetime.date(lastTPobj.year, lastTPobj.month, lastTPobj.day)
		# Iterate over group rows and populate scores
		for i, row in group.iterrows():
			# Get current touchpoint date from the row and convert to date object
			tpDate = datetime.datetime.strptime(row['ga_dateHourMinute'], '%Y%m%d%H%M')
			# Truncate hours and minutes
			tpDateTrunk = datetime.date(tpDate.year, tpDate.month, tpDate.day)
			# Figure out differnce in days
			delta = lastTPTrunk - tpDateTrunk
			# Define curve aggression / decay rate
			# aggression = 0.9
			aggression = 1 - (sliderVal / 100)
			# Apply y = ab(pow) exponensial decay forumla and set med_score variable
			med_score = 100 * math.pow(aggression, delta.days)
			# med_score = math.pow(aggression, delta.days)
			# Print each row/touchpoint score
			# print(f'{row["ga_medium"]} : {delta.days} days : score: {int(med_score)}')
			# set current touchpoint
			currTP = row['ga_dateHourMinute']
			# print(currTP)
			currScore = dfTouchpointsDecayOutput.at[0, row['ga_medium']]
			# Set score by adding existing and current
			dfTouchpointsDecayOutput.at[0, row['ga_medium']] = int(med_score) + currScore
			# get index of tp in dfTouchpoints
			idxs = dfTouchpoints.index[dfTouchpoints['ga_dateHourMinute'] == currTP].tolist()
			# push med_score to dfTouchpoints
			dfTouchpoints.at[idxs, 'score'] = round(med_score, 2)

		# Print end of interation line
		# print(50*'-')

	# Print populated dfTouchpointsDecayOutput with scores
	print(dfTouchpointsDecayOutput)
	print(100*'-')

	# Convert scores to percentages
	dfTouchpointsDecayOutput[mediumsAll] = dfTouchpointsDecayOutput[mediumsAll].div(dfTouchpointsDecayOutput[mediumsAll].sum(axis=1), axis=0) * 100
	# Rename axis and first column
	dfTouchpointsDecayOutput = dfTouchpointsDecayOutput.T.rename_axis('mediums').reset_index().rename(columns={0 : 'weighted tps'}).round(2)
	# Print df in percentages
	print(dfTouchpointsDecayOutput)
	print(100*'-')

	# Calculate average touchpoint / medium
	dfATPM = dfTouchpoints['ga_medium'].value_counts(dropna = False) / dfConverters['ga_medium'].value_counts()
	dfATPM = dfATPM.rename_axis('mediums').reset_index(name='avg tps').sort_values('avg tps', ascending=False).fillna(0).round(2).sort_values('mediums')
	print(dfATPM)
	print(100*'-')

	# Define custom mediums (not in use)
	customCols = ['cpc', 'organic', 'referral', 'direct', 'partner']

	# Buckets new!
	# Extract touchpoint count per medium for each converter
	buckets = ['1 to 2', '3 to 4', '5 to 6', '7+']
	dfBuckets = pd.DataFrame(columns = mediumsAll, index = buckets).fillna(0)
	for converter in converterIDs:
		dfWOW = dfTouchpoints.query('ga_userId == @converter')['ga_medium'].value_counts().rename_axis('medium').reset_index(name='tps')
		medium = dfWOW['medium'].values[0]
		tps = dfWOW['tps'].values[0]
		if dfWOW['tps'].values[0] < 3:
			dfBuckets.at['1 to 2', medium] = dfBuckets.at['1 to 2', medium] + tps
		elif tps > 2 and tps < 5:
			dfBuckets.at['3 to 4', medium] = dfBuckets.at['3 to 4', medium] + tps
		elif tps > 4 and tps < 7:
			dfBuckets.at['5 to 6', medium] = dfBuckets.at['5 to 6', medium] + tps
		elif tps > 6:
			dfBuckets.at['7+', medium] = dfBuckets.at['7+', medium] + tps

	dfBuckets = dfBuckets.reset_index().rename(columns = {'index':'buckets'})
	print(dfBuckets)
	print(100*'-')
	# print(type(dfBuckets))
	
	# Sum up dfBuckets rows
	dfBucketsSum = dfBuckets.sum(axis=1).to_frame().rename(columns = {0:'tps'})
	dfBucketsSum = dfBucketsSum / dfBucketsSum.sum() * 100
	dfBucketsSum.insert(0, 'buckets', buckets)
	print(dfBucketsSum)

	# Campaign Conversions
	# print('Conversions / Campaign...')
	dfCampaignConversions = dfConverters['ga_campaign'].value_counts().rename_axis('Campaign').reset_index(name='Conversions')
	# print(dfCampaignConversions)

	# Campaign Conversion Rates
	dfCampaignRates = dfTouchpoints['ga_campaign'].value_counts() / dfConverters['ga_campaign'].value_counts()
	dfCampaignRates = dfCampaignRates.rename_axis('Campaign').reset_index(name='Conv. Rate %').fillna(0).round(2).sort_values('Conv. Rate %', ascending=False)
	# print(dfCampaignRates)

	print(100*'-')
	print('Pushing data to Google Sheet...')

	# Initialize GSheet
	gc = pygsheets.authorize(service_file='key.json')
	sh = gc.open('mta')

	# Clear all tabs
	for tab in sh:
		tab.clear()

	#Push to GSheet
	sh[0].set_dataframe(dfConverters,(1,1))
	sh[1].set_dataframe(dfTouchpoints,(1,1))
	sh[2].set_dataframe(dfTouchpointsDecayOutput,(1,1))
	sh[3].set_dataframe(dfATPM,(1,1))
	sh[4].set_dataframe(dfBuckets,(1,1))
	sh[5].set_dataframe(dfBucketsSum,(1,1))
	sh[6].set_dataframe(dfCampaignConversions,(1,1))
	sh[7].set_dataframe(dfCampaignRates,(1,1))
	print('Pushed!')

#Main Function
def main(startDate, endDate, viewID, userID, journeyID, sliderVal):
	print(100*'-')
	print(sliderVal)
	analytics = initialize_analyticsreporting()
	response = get_report(analytics, startDate, endDate, viewID, userID, journeyID)
	generate_output(response, userID, journeyID, sliderVal)
	print(100*'-')

#Run Main
if __name__ == '__main__':
	main()