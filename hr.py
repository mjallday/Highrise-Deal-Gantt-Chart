#
#	
#
#
#



from xml.dom.minidom import parse, parseString
import urllib
import urllib2
import base64
import math
import sys
from datetime import datetime, timedelta

hr_username = None
hr_password = 'x'
hr_url = None
output_dir = None

def getText(nodelist):
	rc = ""
	for node in nodelist:
		if node.nodeType == node.TEXT_NODE:
			rc = rc + node.data
	return rc

# create a list of deals from highrise
def load_deals():

	deals = []

	req = urllib2.Request(hr_url)
	
	base64string = base64.encodestring('%s:%s' % (hr_username, hr_password))[:-1]
	req.add_header("Authorization", "Basic %s" % base64string)
	
	try:
		f = urllib2.urlopen(req)
	except urllib2.HTTPError:
		print('Eeep, did you specify a valid Highrise API key (401) or a valid Highrise url (404)?', 'Url should be like https://mycompany.highrisehq.com/deals.xml')
		raise

	deal_dom = parseString(f.read())
	
	for node in deal_dom.getElementsByTagName('deal'):
		deal = {}
		
		deal['name'] = getText(node.getElementsByTagName('name')[0].childNodes)
		deal['created_on'] = getText(node.getElementsByTagName('created-at')[0].childNodes)
		
		# like 2010-08-30T05:34:02Z
		deal['created_on'] = datetime.strptime( deal['created_on'] , '%Y-%m-%dT%H:%M:%SZ')
		
		deal['status'] = getText(node.getElementsByTagName('status')[0].childNodes)
		deal['status_changed_on'] = getText(node.getElementsByTagName('status-changed-on')[0].childNodes)
		
		# like 2010-08-31
		if len(deal['status_changed_on']) > 0:
			deal['status_changed_on'] = datetime.strptime(deal['status_changed_on'], '%Y-%m-%d')
		
		deal['updated-at'] =  datetime.strptime( getText(node.getElementsByTagName('updated-at')[0].childNodes) , '%Y-%m-%dT%H:%M:%SZ')
		
		deals.append(deal)
	
	return deals

# generate a dictionary of information that can be used to request a chart from google
def generate_chart_data(deals, chart_title):

	if len(deals) == 0:
		return None

	# colors
	# buffer (white, transparent), progress (gray), completed (blue), lost (red)
	chco = ['ffffff00', 'cccccc', '4d89f9', 'ff0000']
	# labels
	chdl = [' ', 'In progress', 'Won', 'Lost']
		
	# find date ranges
	min_date = datetime.utcnow()
	max_date = datetime.utcnow()
	
	for deal in deals:
		if deal['created_on'] < min_date:
			min_date = deal['created_on']
		try:	
			if deal['status_changed_on'] > max_date:
				max_date = deal['status_changed_on']
		except TypeError:
			pass
			
	date_diff = max_date - min_date
	total_days = float(date_diff.days)
	#print('Difference in days = %d' % date_diff.days)
			
	chd_buffer = []
	chd_starts = []
	chd_lost = []
	chd_winner = []
	chxl = []
	chyl = []
	
	
	for deal in deals:
		#first point is diff between min_date and created_on (when the deal started)		
		days = (deal['created_on'] - min_date).days
		
		# google charts are a percentage so we need to calculate this
		days = math.floor(days / total_days * 100)
				
		chd_buffer.append(str(days))
		
		# second point is diff between created_on and status_updated_on, 
		# if status_updated_on doesn't exist it means the deal is still live
		end_date = deal['status_changed_on']
		
		if end_date == '':
			end_date = datetime.utcnow()
		
		days = (end_date - deal['created_on']).days
		
		# if a deal is created today or created and closed on the same day it will not display unless we give it a value here
		if days < 1:
			days = 1
			
		days = math.ceil(days / total_days * 100)
		
		if deal['status'] == 'won':
		
			chd_starts.append('0')	
			chd_winner.append(str(days))	
			chd_lost.append('0')

		elif deal['status'] == 'lost':
		
			chd_starts.append('0')	
			chd_winner.append('0')				
			chd_lost.append(str(days))
			
		else:
		
			chd_starts.append(str(days))			
			chd_winner.append('0')			
			chd_lost.append('0')
		
		chyl.append(deal['name'])
		
		
	# add a date label every x days
	for day in range(int(total_days)):
		if day == 0 or day % 14 == 0 or day == int(total_days) - 1:
			chxl.append((min_date + timedelta(days=day)).strftime('%d-%m'))
			
			
	# calculate chart area, max 300,000 px
	chart_width = 600
	max_height = 500
	line_height = 25 # each line needs about 25px
	lines = len(chyl)
	
	height = lines * line_height + (25 * 3) # extra two lines for the title and bottom axis labels
	
	if height > max_height:
		height = max_height
		print ('max height reached, data may be truncated')

	chart_data = {}
	
	# type
	chart_data['cht'] = 'bhs'
	# size
	chart_data['chs'] = str(chart_width) + 'x' + str(height)
	# data
	chart_data['chd'] = 't:' + ','.join(chd_buffer) + '|' + ','.join(chd_starts) + '|' + ','.join(chd_winner) + '|' + ','.join(chd_lost)
	# scale
	chart_data['chds'] = '0,100'
	# axis
	chart_data['chxt'] = 'x,y'
	# axis labels
	chart_data['chxl'] = '0:|' + '|'.join(chxl) + '|1:|' + '|'.join(chyl)
	# color
	chart_data['chco'] = ','.join(chco)
	# legend
	chart_data['chdl'] = '|'.join(chdl)
	# grid lines
	chart_data['chg'] = '7.1,0'
	# title
	chart_data['chtt'] = chart_title
	
	return chart_data

# request a chart from google
def generate_graphic(chart_data, chart_name):

	if chart_data is None:
		print ('no deals, no graph')
		return

	req = urllib2.Request('http://chart.apis.google.com/chart',  urllib.urlencode(chart_data))

	f = urllib2.urlopen(req)

	try:
		with open(output_dir + chart_name + '.png', 'wb') as img:
			img.write(f.read())
	except IOError:
		print('Did you specify a valid output direction with a *trailing* slash?', 'C:\\temp\\', '/var/tmp/')
		raise

def main():

	deals = load_deals()	

	lost_deals = filter(lambda deal: deal['status'] == 'lost', deals)
	lost_deals = generate_chart_data(lost_deals, 'Lost Deals')
	generate_graphic(lost_deals, 'lost_deals')

	pending_deals = filter(lambda deal: deal['status'] == 'pending', deals)
	pending_deals = generate_chart_data(pending_deals, 'Pending Deals')
	generate_graphic(pending_deals, 'pending_deals')

	# alt syntax - lambda vs list comprehension
	won_deals = filter(lambda deal: deal['status'] == 'won', deals)
	#won_deals = [deal for deal in deals if deal['status'] == 'won']

	won_deals = generate_chart_data(won_deals, 'Won Deals')
	generate_graphic(won_deals, 'won_deals')


	deals = generate_chart_data(deals, 'All Deals')
	generate_graphic(deals, 'deals')
 
if __name__ == "__main__":

	if len(sys.argv) < 4:
		print "Usage: hr.py <highrise_api_key> <highrise_url> <output_dir>"
		sys.exit(0)
		
	hr_username = sys.argv[1]
	hr_url = sys.argv[2]
	output_dir = sys.argv[3]
		
	main()
