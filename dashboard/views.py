from django.views.generic import TemplateView
from BeautifulSoup import BeautifulSoup
import re
import urllib, urllib2
import time
import os

ci_url = "http://ci.apps-system.com/"
base_url = "%s/job" % ci_url

builds = [
    'django-admin-ext',
    'django-dynamic-rules',
    'django-dynamic-validation',
    'django-forms-ext',
    'django-dynamic-manipulation',
    'django-wizard',
    'django-pretty-times',
    'django-response-helpers',
    'django-attachments',
]

class Stats(TemplateView):
    template_name = 'dashboard/stats.html'

    def get_projects_table(self):
        request = urllib2.Request(ci_url)
        request.add_header("Authorization", "Basic %s" % os.environ['CIAUTH'])
        f = urllib2.urlopen(request)
        data = f.read()
        f.close()
        page = BeautifulSoup(data)
        project_table = page.findAll(**{'id': 'projectstatus'})[0]

        return project_table.findAll('tr')[1:]

    def get_projects(self, projects_table):
        projects = []
        for project in projects_table:
            if dict(project.attrs).get('id', "").startswith('job_'):
                projects.append(project.find(**{'class': 'model-link'}).text)

        return projects

    def get_coverage_stats(self, projects_table):
        projects = self.get_projects(projects_table)

        coverage_data = {}
        for project in projects:
            f = urllib.urlopen("{}/job/{}/cobertura/".format(ci_url, project))
            data = f.read()
            if data:
                page = BeautifulSoup(data)
                greenbar = page.findAll(**{'class': 'greenbar'})
                if greenbar:
                    coverage_data[project] = greenbar[3].find(**{'class': 'text'}).text.split('/')

        all_covered = 0.0
        all_total = 0.0
        coverage = []

        for project, (covered, total) in coverage_data.items():
            coverage.append((project, int((float(covered) / float(total)) * 100)))
            all_covered += int(covered)
            all_total += int(total)

        return {
            'total_lines': int(all_total),
            'total_lines_covered': int(all_covered),
            'total_coverage': int((all_covered / all_total) * 100),
            'project_coverage': coverage,
        }

    def get_test_stats(self, projects_table):
        test_data = {}
        for p in projects_table:
            if dict(p.attrs).get('id', "").startswith('job_'):
                project = p.find(**{'class': 'model-link'}).text
                health_report = p.findAll(**{'class': 'healthReportDetails'})
                if health_report:
                    for row in health_report[0].findAll('tr'):
                        if row.text.startswith('Test Result:'):
                            test_message = row.findAll('td')[-2].text
                            match = re.search('total of ([\d,]+) tests', test_message)
                            test_data[project] = re.sub(',', '', match.group(1))

        return {
            'total_tests': sum(int(v) for v in test_data.values()),
            'project_tests': test_data,
        }

    def get_context_data(self, **kwargs):
        projects_table = self.get_projects_table()
        combined_data = dict(
            coverage=self.get_coverage_stats(projects_table),
            test=self.get_test_stats(projects_table),
            projects={},
        )

        for project, coverage_data in combined_data['coverage']['project_coverage']:
            combined_data['projects'][project] = {
                'coverage': coverage_data,
                'test': combined_data['test']['project_tests'][project]
            }

        return combined_data

class Status(TemplateView):
    template_name = 'dashboard/status.html'

    def get_context_data(self, **kwargs):
        request = urllib2.Request(ci_url)
        request.add_header("Authorization", "Basic %s" % os.environ['CIAUTH'])
        f = urllib2.urlopen(request)
        data = f.read()
        f.close()
        page = BeautifulSoup(data)

        status_table = page.findAll(**{'id': 'projectstatus'})[0]
        statuses = []
        for cell in status_table.findAll('tr')[1:]:
            status_icon = cell.find('img', **{'class': 'icon32x32'})
            if status_icon:
                statuses.append(dict(status_icon.attrs)['alt'])

        ss = [s not in ('Success', 'Disabled', 'In progress', 'Pending') for s in statuses]
        fail = any(ss)
        if fail:
            for i in range(20):
                print "\a"
                time.sleep(.2)

        return {'success': not fail}

class Index(TemplateView):
    template_name = 'dashboard/index.html'
    current_build = -1

    def get_context_data(self, **kwargs):
        Index.current_build += 1
        if Index.current_build >= len(builds):
            Index.current_build = 0

        build = builds[Index.current_build]
        return {
            'params': kwargs,
            'status':self.get_status(),
            'build': build,
            'test_section_title':'Tests',
            'test_section_content':self.get_test_graph(build),
            'coverage_section_title':'Coverage',
            'coverage_section_content':self.get_cobertura_graph(build),
            'violations_section_title':'Violations',
            'violations_section_content':self.get_violations_graph(build),
            'pylint_section_title':'Pylint',
            'pylint_section_content':self.get_pylint_graph(build),
            'cpd_section_title':'CPD',
            'cpd_section_content':self.get_cpd_graph(build),
            'pep8_section_title':'Pep8',
            'pep8_section_content':self.get_pep8_graph(build),
        }

    def get_status(self):
        page = get_build_page(builds[Index.current_build] + "/lastBuild")
        status = get_status(page)
        return status.replace(" ", '')

    def get_test_graph(self, build):
        return "%s/%s/test/trend" % (base_url, build)

    def get_cobertura_graph(self, build):
        return "%s/%s/cobertura/graph" % (base_url, build)


    def get_violations_graph(self, build):
        return "%s/%s/violations/graph" % (base_url, build)

    def get_pylint_graph(self, build):
        return "%s/%s/violations/graph?type=pylint" % (base_url, build)

    def get_cpd_graph(self, build):
        return "%s/%s/violations/graph?type=cpd" % (base_url, build)

    def get_pep8_graph(self, build):
        return "%s/%s/violations/graph?type=pep8" % (base_url, build)

def get_build_page(build):
    f = urllib.urlopen("%s/%s/" % (base_url, build))
    page = f.read()
    f.close()
    return BeautifulSoup(page)

def get_coverage(page):
    return page.findAll(text=re.compile("Cobertura Coverage"))[0]

def get_test_results(page):
    return page.findAll(text=re.compile("Test Result:"))[0]

def get_status(page):
    return page.findAll(src="buildStatus")[0]['alt']


#def get_violation_results(violation_type, page):
#    violation = page.find('a', {'href':'#' + violation_type})
#    violation_count = violation.parent.nextSibling
#    return (violation_count.text, violation_count.nextSibling.text)

#def get_image_html(src):
#    return r"<img src='%s' />" % src

#def get_section(title, content):
#    return """
#        <div class="column">
#            <div class="section">
#                <h2>%s</h2>
#                %s
#            </div>
#        </div>
#    """ % (title, content)
#
#def build_stats(build):
#
#    #build, status
#
##    print get_section("CPD", get_image_html(get_cpd_graph(build)))
##    print get_section("Pep8", get_image_html(get_pep8_graph(build)))
##    print """<div style="clear:both;" />"""
#
#
#def x():
#    for build in builds:
#        build_stats(build)
