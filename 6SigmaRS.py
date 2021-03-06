# -*- coding: utf-8 -*-
"""
Created on Thu Jun 23 16:51:10 2016

@author: pawel.cwiek
"""

# ElementTree is the fastest and uses least memory for parsing xml (even better is cElementTree)

#import xml.etree.ElementTree as ET
#
#cabs_xml = ET.parse('cabs.xml')
#
#cabs = cabs_xml.findall('type')
#for item in cabs.iter('urn:schemas-microsoft-com:office:spreadsheet'):
#    print(item)

# http://docs.python-guide.org/en/latest/scenarios/xml/

# ------ using xmltodict because of particular msExcell XML format generated by 6Sigma

#import xmltodict
#
#with open('cabs.xml') as fd:
#    cabs = xmltodict.parse(fd.read())
#
#sheet = cabs['Workbook']['Worksheet']['Table']['Row']

# xmltodict does not work well with MS xml

# ------ using xml.sax

import logging
import copy
#logging.basicConfig(level=logging.INFO)
import os
from time import strftime
log_path = os.path.join(os.getcwd(),'6SigmaRS.log')
print(log_path)
logg_config = dict([('level',logging.INFO)])
logg_config.update(dict([('filename',log_path),('filemode','w')]))
logging.basicConfig(**logg_config)

from xml.sax import saxutils
from xml.sax import parse

# just to have neat console prints for checks/testing
import pprint
pp = pprint.PrettyPrinter(indent=1, depth=2)
printout = pp.pprint

import tkinter.tix as tk
import tkinter.ttk as ttk
import tkinter.filedialog

import leather

import write_stats

class ExcelHandler(saxutils.XMLGenerator):
    def __init__(self):
        saxutils.XMLGenerator.__init__(self)
        self.chars=[]
        self.cells=[]
        self.rows=[]
        self.tables=[]

    def characters(self, content):
        self.chars.append(content)

    def startElement(self, name, atts):
        if name=="Cell":
            self.chars=[]
        elif name=="Row":
            self.cells=[]
        elif name=="Table":
            self.rows=[]

    def endElement(self, name):
        if name=="Cell":
            self.cells.append(''.join(self.chars))
        elif name=="Row":
            self.rows.append(self.cells)
        elif name=="Table":
            self.tables.append(self.rows)

def parse_6sigma_xml(server_filepath,relevant_server_cols):
    '''
    wrapper over xml.sax
    returns [servers] - list of dicts
    '''
    import functools
    # print(server_filepath,relevant_server_cols)
    serversHandler=ExcelHandler()

    parse(server_filepath, serversHandler)

    servers_header = serversHandler.tables[0].pop(0)
    logging.info('XML header: [ {} ]'.format(servers_header))
    # clean-up header names parsed from xml
    repls = (('\n', ''), (' ', ''))
    for no, item in enumerate(servers_header):
        servers_header[no] = functools.reduce(lambda a, kv: a.replace(*kv), repls,servers_header[no])

    # get column index number of each relevant/needed column (out of all columns available)
    server_cols_filter = relevant_server_cols.copy()
    for key, value in server_cols_filter.items():
        server_cols_filter[key] = servers_header.index(value)

    # get only relevant values from all rows available in xml and assign their column names via dict
    servers = extract_values(serversHandler.tables[0],server_cols_filter)

    return servers

def extract_values(unfiltered_row_list,filter_dict):
    '''
    returns list of dicts with key,value pairs only as per filter_dict
    i.e. list of cabinet instances. each instance is represented with a dict and only having keys per filter_dict
    '''
    filters = filter_dict
    item_list=[]

    logging.info('filters to be applied(which columns will be copied): [ {} ]'.format(filters))
    #logging.info('unfiltered raw row: [ {} ]'.format(unfiltered_row_list))

    for row in unfiltered_row_list:
        item = filters.copy()
        for parameter,index in item.items():
            try:
                value = float(row[index])
            except:
                value = row[index]
            item[parameter] = value
        item_list.append(item)
    return item_list

def calc_report_old(cabs,servers,max_temp):
    from collections import OrderedDict

    condition = 'over_{}degC'.format(max_temp)

    report = OrderedDict([
              (condition+'_cabs',None),
              ('total_cabs',None),
              (condition+'_servers',None),
              ('total_servers',None),
              ('average_mean_servers_temp_in',None),
              ('average_max_servers_temp_in',None),
              ('percent_servers_overheating',None)
              ])
    # report.update()

    report['total_cabs'] = len(cabs)

    report[condition+'_cabs'] = len([True for item in cabs if item['mean_temp_in'] > max_temp])
#    print(sorted([item['mean_temp_in'] for item in cabs if item['mean_temp_in'] > max_temp]))
    report['total_servers'] = len(servers)
    report[condition+'_servers'] = len([True for item in servers if item['mean_temp_in'] > max_temp])
    report['percent_servers_overheating'] = float("{0:.1f}".format(report[condition+'_servers']*100 / report['total_servers']))

    temps = [item['mean_temp_in'] for item in servers]
    report['average_mean_servers_temp_in'] = float("{0:.1f}".format(sum(temps) / len(servers)))

    report['max_mean_servers_temp_in'] = float("{0:.1f}".format(max(temps)))

    return report

def calc_report(file_path,max_temp,servers=None):
    from collections import OrderedDict
    import os

    condition = 'over_{}degC'.format(max_temp)

    report = OrderedDict([
              ('filename',file_path.split(os.sep)[-1]),
              ('room_heat_load_kW',None),
              (condition+'_cabs',None),
              ('total_cabs',None),
              (condition+'_servers',None),
              ('total_servers',None),
              ('average_mean_servers_temp_in',None),
              ('max_mean_servers_temp_in',None),
              ('max_servers_temp_in',None),
              ('percent_servers_overheating',None)
              ])
    details = OrderedDict([
              ('filename',file_path.split(os.sep)[-1])
              ])
    for temp in range(15,40,1):
        details[str(temp+0.5)] = None

    if servers is None:
        output = (report,details)
        return output
    
    server_temp_counts = OrderedDict()
    for temp in range(15,40,1):
        server_temp_counts[str(temp+0.5)] = 0

    for server in servers:
        temp = server['mean_temp_in']
        server_temp_counts[str(int(temp)+0.5)] += 1

    details.update(server_temp_counts)                           
                           
    server_temps_by_cabs = dict()
    for server in servers:
        location = server['location'].split(':')[0]
        location = location.replace(' \n','')
        try:
            server_temps_by_cabs[location] = server_temps_by_cabs[location] + [server['mean_temp_in']] * int(server['u_height'])

        except KeyError:
            server_temps_by_cabs[location] = [server['mean_temp_in']] * int(server['u_height'])

    cabs_mean_temp = {item[0]:sum(item[1])/len(item[1]) for item in server_temps_by_cabs.items()}
    cabs_mean_over_max = {key:value for key,value in cabs_mean_temp.items() if float("{0:.2f}".format(value)) > max_temp}

    '''
    # check of cabinet mean temp calcs
    for key,value in server_temps_by_cabs.items():
        printout('{}({}): {}'.format(key,len(value),value))

    import operator
    printout(sorted(cabs_mean_over_max.items(),key=operator.itemgetter(1)))
    '''

    report['total_cabs'] = len(cabs_mean_temp.keys())
    report[condition+'_cabs'] = len(cabs_mean_over_max.keys())

    report['total_servers'] = len(servers)
    report[condition+'_servers'] = len([True for item in servers if item['mean_temp_in'] > max_temp])
    report['percent_servers_overheating'] = float("{0:.1f}".format(report[condition+'_servers']*100 / report['total_servers']))

    temps = [item['mean_temp_in'] for item in servers]
    report['average_mean_servers_temp_in'] = float("{0:.1f}".format(sum(temps) / len(servers)))

    report['max_mean_servers_temp_in'] = float("{0:.1f}".format(max(temps)))

    max_temps = [item['max_temp_in'] for item in servers]
    report['max_servers_temp_in'] = float("{0:.1f}".format(max(max_temps)))

    heat_loads = [(item['name_plate_power']*item['heat_power_ratio']/100) for item in servers]
    report['room_heat_load_kW'] = float("{0:.1f}".format(sum(heat_loads)))
    
    output = (report,details)
    return output

def find_xmls(dir_path):
    # returns list of filepaths including only xml files (no subfolders)
    import os

    files = [fn for fn in next(os.walk(dir_path))[2] if fn.count('.xml')]

    return [os.path.join(dir_path,fn) for fn in files]

def reports_to_csv(mypath, rows):
    import csv

    with open(mypath, 'a') as csvfile:
        mywriter = csv.DictWriter(csvfile, rows[0].keys(), delimiter=',', lineterminator='\n', quoting=csv.QUOTE_MINIMAL, dialect='excel', extrasaction='ignore')
        mywriter.writeheader()
        for simulation in rows:
            mywriter.writerow(simulation)

    return mypath

def calc_one_file(dir_path,cab_cols_filter,server_cols_filter,max_temp):
    import os

    cabs_filename = 'cabs.xml'
    servers_filename = 'servers.xml'

    cabs,servers = parse_6sigma_xml_old(os.path.join(dir_path,cabs_filename),os.path.join(dir_path,servers_filename),cab_cols_filter,server_cols_filter)
    report = calc_report_old(cabs,servers,max_temp)
    return [report]

def calc_bulk_files(server_cols_filter,max_temp,dir_path):
    reports = []
    server_temp_counts = []
    file_paths_list = find_xmls(dir_path)
    #logging.INFO('XMLs found: [%r]' % (item)) for item in file_paths_list
    for file_path in file_paths_list:
        try:
            servers = parse_6sigma_xml(file_path,server_cols_filter)
            logging.info('file [ {} ] - data parsed(first row): [ {} ]'.format(file_path,servers[0]))
            output = calc_report(file_path,max_temp,servers)
            report,details = output[0], output[1]
            reports.append(report)
            server_temp_counts.append(details)
        except Exception as e:
            logging.warning('error calculating report for [%s]: %r' % (file_path,e))
            logging.warning('perhaps User edited&saved file in another program ie MS Excel')
            raise
    return (reports,server_temp_counts)

class PixelLabel(ttk.Frame):
    def __init__(self,master, w, h=20, *args, **kwargs):
        '''
        creates label inside frame,
        then frame is set NOT to adjust to child(label) size
        and the label keeps extending inside frame to fill it all,
        whatever long text inside it is
        '''
        ttk.Frame.__init__(self, master, width=w, height=h)
        self.grid_columnconfigure(0, weight=1)
        self.grid_propagate(False) # don't shrink
        self.label = ttk.Label(self, *args, **kwargs)
        self.label.grid(sticky='nswe')

    def resize(self,parent,*other_childs):
        '''
        resizes label to take rest of the width from parent
        that other childs are not using
        '''
        parent.update()
        new_width = parent.winfo_width()

        for widget in other_childs:
            widget.update()
            new_width -= widget.winfo_width()

        self.configure(width = new_width)

class MyGui(object):
    def __init__(self,root,server_filter):
        self.reports = []
        self.server_temp_counts = []
        self.path = ''
        self.server_cols_filter = server_filter
        self.dir_frame = ttk.Frame(root)
        self.dir_frame.grid()

        intro_txt = 'This little app helps to summarise multiple XML result files for IT Equipment(servers) exported from 6Sigma CFD simulation software.'
        self.introlbl = ttk.Label(self.dir_frame, justify="left", anchor="n", padding=(10, 2, 10, 6), text=intro_txt)
        self.introlbl.grid(row=0)

        self.top_frame = ttk.Frame(self.dir_frame)
        self.top_frame.grid(row=1)

        self.controls_frame = ttk.Frame(self.top_frame)
        self.controls_frame.grid(row=1,column=0,sticky='e')

        self.dir_path = tk.StringVar()
        self.folder_lbl = ttk.Label(self.controls_frame, justify="left", anchor="w", text='Result xml files location:')
        self.folder_lbl.grid(row=1,column=0,sticky='e')
        self.path_entry = ttk.Entry(self.controls_frame, textvariable=self.dir_path,width=50)
        self.path_entry.grid(row=1,column=1,sticky='we', padx=(5, 5))
        self.browse_btn = ttk.Button(self.controls_frame, command = self.browse_dir, text = 'Browse')
        self.browse_btn.grid(row=1,column=2)

        self.temp_lbl = ttk.Label(self.controls_frame, justify="left", anchor="e", text='Max. server inlet temp. [degC]:')
        
        self.temp_spiner = tk.Spinbox(self.controls_frame, from_=15, to=40, increment=0.5,width=5)        
        for i in range(0,(27-15)*2): self.temp_spiner.invoke('buttonup')
            
        self.temp_lbl.grid(row=2,column=0,sticky='e')
        self.temp_spiner.grid(row=2,column=1,sticky='w', padx=(5, 5))

        self.navi_frame = ttk.Frame(self.top_frame)
        self.navi_frame.grid(row=1,column=1, padx=(10, 10),pady=(0,10),sticky='w')

        self.calc_btn = ttk.Button(self.navi_frame, text = 'Calculate', command = self.gui_calc)
        self.calc_btn.grid(row=0,sticky='nsew')
        self.export_btn = ttk.Button(self.navi_frame, text = 'Export to CSV', command = self.gui_export_csv)
        self.export_btn.grid(row=1,sticky='nsew')
        self.export_btn = ttk.Button(self.navi_frame, text = 'Help', command = self.show_help)
        self.export_btn.grid(row=2,sticky='nsew')
        self.close_btn = ttk.Button(self.navi_frame, command = lambda: root.destroy(), text = 'Close')
        self.close_btn.grid(row=3,sticky='nsew')
        
        self.tree_headers()
        self.update_tree_views()

        self.botom_frame = ttk.Frame(self.dir_frame)
        self.botom_frame.grid(row=6)

        status_txt = "Browse for folder containing multiple XML files (only 6Sigma 'IT Equipment' PropertyTable export files will be filtered off for analysis), set max. temp SLA threshold. Then click 'Calculate'"
        self.status_lbl = PixelLabel(self.botom_frame, 1, borderwidth=1, relief='sunken', background='#D9D9D9', text = status_txt)
        self.status_lbl.grid(row=3,sticky='w',column=0)
        # self.status_lbl.grid(row=3,sticky='nsew',columnspan=1,wraplenght='4i')

        self.brag = ttk.Label(self.botom_frame, text = "about", borderwidth=1, relief='sunken', background='#D9D9D9',width=6)
        self.brag.grid(row=3,column=1,sticky='e')

        self.status_lbl.resize(root,self.brag)

        # root.tk.call("load", "", "Tix")
        self.baloon = tk.Balloon()
        self.baloon.bind_widget(self.brag, balloonmsg='ver1.2 created in Warsaw by pawel.cwiek@arup.com')
    
    def update_tree_views(self,destroy=False):
        if destroy:
            for i in self.tree_widgets:
                i.destroy()
            return
        self.tree_lbl = ttk.Label(self.dir_frame, justify="left", anchor="e", text='Summary:')
        self.tree_lbl.grid(row=2,sticky='w')
        self.tree = self.create_tree_view(self.dir_frame,self.reports).container
        self.tree.grid(row=3)

        self.tree_details_lbl = ttk.Label(self.dir_frame, justify="left", anchor="e", text='Server count for each "MeanTemperatureInC"(+/-0.5C):')
        self.tree_details_lbl.grid(row=4,sticky='w')
        
        self.dtree_frame = ttk.Frame(self.dir_frame)
        self.dtree_frame.grid(row=5,sticky='w')
        self.tree_details = self.create_tree_view(self.dtree_frame,self.server_temp_counts).container
        self.tree_details.grid(row=0,column=0,sticky='w')
        self.chart_btn = ttk.Button(self.dtree_frame, text = 'Generate chart', command = self.generate_chart)
        self.chart_btn.grid(row=0,column=1,sticky='nw')
        
        self.tree_widgets = [self.tree_lbl,self.tree,self.tree_details_lbl,self.dtree_frame]
        return None
        
    def create_tree_view(self,master,results):
        import tkTreeWitget
        headers = [key for key in results[0].keys()]
        mc_listbox = tkTreeWitget.McListBox(master, headers)

        if list(results[0].values())[0] == '':
            results = []
            return mc_listbox

        values_list = []
        for item in results:
            values = [value for key,value in item.items()]
            values_list.append(tuple(values))

        mc_listbox.build_values(values_list)
        return mc_listbox

    def browse_dir(self):
        options = {}
        options['initialdir'] = self.dir_path.get()
        options['mustexist'] = True
        options['title'] = '6Sigma XML result files folder:'
        self.dir_path.set(tkinter.filedialog.askdirectory(**options))

    def calc_reports(self):
        max_temp = float(self.temp_spiner.get())
        
        output = calc_bulk_files(self.server_cols_filter,max_temp,self.path)
        self.reports, self.server_temp_counts = output[0], output[1]
        if self.reports == []: self.tree_headers()
        write_stats.dump_stats(self.reports)

    def finish_calc(self):
        if self.calc_thread.is_alive():
            root.after(500,master.finish_calc)
        else:
            self.progress_bar.stop()
            self.progress_bar.destroy()

            self.update_tree_views()
            
            if self.reports[0]['filename'] != '':
                txt = 'Calculation finished. Number of correct files found and processed: {}'.format(len(self.reports))
            else:
                txt = 'No files found in specified location'
            self.status_lbl.label.configure(text=txt)
            root.update()
            self.status_lbl.resize(root,self.brag)

    def gui_calc(self):
        import threading

        self.path = self.dir_path.get()

        self.update_tree_views(destroy=True)

        self.progress_bar = ttk.Progressbar(self.dir_frame,orient='horizontal',mode='indeterminate')
        self.progress_bar.grid(row=2)
        self.progress_bar.start()

        self.calc_thread = threading.Thread(target=self.calc_reports)
        self.calc_thread.deamon = True
        self.calc_thread.start()
        root.after(500,master.finish_calc)


    def gui_export_csv(self):
        self.path = self.dir_path.get()
        #self.status_lbl.configure(text=self.path)
        filepath = os.path.join(self.path,strftime('%Y-%m-%d_%H%M%S') + '-bulk_6Sigma_results'+'.csv')
        reports_to_csv(filepath, self.reports)
        reports_to_csv(filepath, self.server_temp_counts)
        txt = 'CSV file succesfully exported to: {}'.format(filepath)
        self.status_lbl.label.configure(text=txt)

    def tree_headers(self):
        self.reports = []
        self.server_temp_counts = []
        blank = calc_report('','')
        self.reports.append(blank[0])
        self.server_temp_counts.append(blank[1])
        return None
        
    def generate_chart(self):
        import webbrowser
        from colors import palette48_iwanthue as palette
        if self.server_temp_counts[0]['filename'] == '':
            txt = 'Nothing to plot'
            self.status_lbl.label.configure(text=txt)
            return None
        if len(self.server_temp_counts) > len(palette):
            txt = 'Plotting only avaialble for max %d files'.format(len(palette))
            self.status_lbl.label.configure(text=txt)
            return None
            
        filepath = os.path.join(self.path,'results_chart.svg')
        max_temp = float(self.temp_spiner.get())
        colors = ['rgb(%i, %i, %i)' % (color[0],color[1],color[2]) for color in palette]
        leather.theme.default_series_colors = colors
        
        name = self.path.split('/')[-1]
        name = self.path.split('\\')[-1]
        chart = leather.Chart('Results for: '+name)
        chart.add_x_scale(15, 40)
        chart.add_x_axis(ticks=[i for i in range(15,40)])
        ymax = 0
        
        details = copy.deepcopy(self.server_temp_counts)
        for file, color in zip(details,palette):
            name = file['filename'][:-4]
            del file['filename']
            data = []
            for x,y in file.items():
                data.append((float(x),y))
                ymax = max(ymax,y)
            #color = 'rgb(%i, %i, %i)' % (color[0],color[1],color[2])
            chart.add_line(data,name=name,width=1)
        
        name = '%ddegC limit' % max_temp
        chart.add_line([(max_temp,0),(max_temp,ymax)],name=name,width=.5,stroke_color='rgb(105,105,105)')
        
        chart.to_svg(filepath)
        url = "file://%s" % filepath
        webbrowser.open(url,new=2)
    
    def show_help(self):
        info_text = '''
        The tool helps to summarise simulation results extracted from 6Sigma-Room Data Centre Simulation software.
        
        It can take server data out from 'IT Equipment' PropertyTable export (xml file)
        and present it summarised in tabular and graphical way for comparision of multiple solutions (multiple xml files)
        
        Usage:
            1) Specify path to the directory where your result xml files are located.
               Tool should automatically select only proper PropertyTable files and filter off remaining files in folder.
               It will not go into subfolders searching for files.
            2) Specify maximum inlet temperature for servers (max. 'MeanTemperatureInC' value accepted).
            3) Click 'Calculate'.
            4) The results will be presented in two tables:
                a) Summary/Statistics for each file in corelation to max. temperature
                b) Detailed results: server count for range of <15;40> degC with 1degC step
                   (eg. '<16;17) degC') - middle of each inverval is shown for convinience
            5) Now you can 'Generate chart' for detailed results
               - file will be saved as 'results_chart.svg'(vector graphics, open via web browser) in folder with xml files
            6) If needed you can export data to csv file
               - file will be saved as '(current date)bulk_6Sigma_results.csv' (can be opened in MS Excel)
        
        This release(1.2) works with 6Sigma ver9 and above (lower versions not supported - look for Results Summariser v1.1) !!
        Created by Pawel Cwiek @ Arup Warsaw
        '''
        toplevel = tkinter.Toplevel()
        toplevel.title='Help'
        label1 = tkinter.Label(toplevel, text=info_text, height=0, width=100, justify="left")
        label1.pack()
                
if __name__ == '__main__':

    import os
    # values in filter dict can not have spaces or '\n' newlines. eg. 'CamelCaseNoSpaces%'
    cab_cols_filter = {'kWe_installed':'CabinetPowerkW',
                       'mean_temp_in':'MeanTemperatureInC'
                       }
    server_cols_filter = {'location':'LocationID',
                          'u_height':'HeightU',
                           'name_plate_power':'NamePlatePowerkW',
                           'heat_power_ratio':'HeatPowerFactor%',
                           'mean_temp_in':'MeanTemperatureInC',
                           'max_temp_in':'MaxTemperatureInC'
                           }
    #max_temp = 27.0
    #reports = []
    #dir_path = os.getcwd()

#    dir_path = 'C:/Python34/WinPython-32bit-3.4.3.6/_my projects/6Sigma results/_old'
#    reports.extend(calc_one_file(dir_path,cab_cols_filter,server_cols_filter,max_temp))

    #dir_path = 'C:/Python34/WinPython-32bit-3.4.3.6/_my projects/6Sigma results'
    #reports.extend(calc_bulk_files(server_cols_filter,max_temp,dir_path))

    root = tk.Tk()
    root.wm_title("6Sigma Results Summarizer")
    root.resizable(0,0)
    master = MyGui(root,server_cols_filter)

    root.mainloop()

    # reports_to_csv(dir_path,reports)

    #dir_path = 'C:/install'
    #printout(cabs)
    #printout(servers)
    #a = calc_report(cabs,servers,27.0)
    #b = calc_report(cabs,servers,26.0)

    #reports_to_csv(dir_path,[a,b])

    #printout(summarise(cabs,servers,27.0))
