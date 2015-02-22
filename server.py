__author__ = 'vyakoviv'


import re
import json

from flask import Flask, render_template, request

from db import AggregationDB, MyMongoClient
from config import config


server = Flask(__name__)
server.config.update(config)


def get_db(project=None):

    if project:
        return AggregationDB(hostname=server.config['db_hostname'],
                             port=server.config['db_port'],
                             project=project)
    return MyMongoClient(hostname=server.config['db_hostname'],
                         port=server.config['db_port'])


@server.route('/')
def root():

    db = get_db()
    projects = db.get_project_names()
    latest_sprints = dict((project, db.get_latest_sprint_name(project)) for project in projects)
    return render_template('base.html', projects=projects, latest_sprints=latest_sprints)


@server.route('/manual', methods=['POST', 'GET'])
def manual_tc():
    db = get_db()
    m_projects = db.get_m_projects()

    if request.method == 'GET':
        return render_template('manual_tc.html', m_projects=m_projects)


@server.route('/manual/<m_project>', methods=['POST', 'GET'])
def manual_suits(m_project):
    db = get_db(m_project)
    m_projects = db.get_m_projects()
    components = db.get_manual_component_names()
    if request.method == 'GET':
        return render_template('manual_suits.html',
                               m_projects=m_projects,
                               m_project=m_project,
                               components=components)


@server.route('/manual/<m_project>/<m_component>')
def manual_tests_suites(m_project, m_component):
    db = get_db(m_project)
    projects = db.get_m_projects()
    m_components = db.get_manual_component_names()
    tests = db.get_manual_tests(component=m_component)
    if not tests:
        return 'I don\'t have tests for this component... Sorry... :/', 404
    # tests.sort(key=lambda x: x['name'])
    return render_template('manual_tests_suites.html',
                           data=tests,
                           project=m_project,
                           projects=projects,
                           component=m_component,
                           components=m_components)

@server.route('/<project>/<sprint>')
def results(project, sprint):

    db = get_db(project)

    projects = db.get_project_names()
    if project not in projects:
        return 'I don\'t have results for this project... Sorry... :/', 404

    sprints = db.get_sprint_names()
    if sprint not in sprints:
        return 'I don\'t have results for this sprint... Sorry... :/', 404
    sprints.remove(sprint)

    test_results = db.get_test_results(sprint)
    components = set([r['component'] for r in test_results])

    components_data = []
    for component in components:
        component_data = {'name': component}

        tests = [r for r in test_results if r['component'] == component]

        component_data['total'] = len(tests)
        component_data['passed'] = len([t for t in tests if t['result'] == 'passed'])
        component_data['failed'] = len([t for t in tests if t['result'] != 'passed'])
        components_data.append(component_data)

    totals = dict()
    totals['total'] = len(test_results)
    totals['passed'] = len([t for t in test_results if t['result'] == 'passed'])
    totals['failed'] = len([t for t in test_results if t['result'] != 'passed'])

    # Failed tests.
    failed_tests = [tr for tr in test_results if tr['result'] != 'passed']
    regex = re.compile('[\'\"\(\)\[\]\.,\+\s\*@#\$%\^&\?]')
    for failed_test in failed_tests:
        failed_test['component_modified'] = re.sub(regex, '-', failed_test['component'])

    return render_template('results.html',
                           components=components_data,
                           totals=totals,
                           project=project,
                           projects=projects,
                           sprint=sprint,
                           sprints=sprints,
                           failed_tests=failed_tests)


@server.route('/<project>/<sprint>/<component>')
def results_suites(project, sprint, component):

    db = get_db(project)
    test_results = db.get_test_results(sprint, component=component)
    suite_names = set([s['suite'] for s in test_results])

    projects = db.get_project_names()
    if project not in projects:
        return 'I don\'t have results for this project... Sorry... :/', 404

    sprints = db.get_sprint_names()
    if sprint not in sprints:
        return 'I don\'t have results for this sprint... Sorry... :/', 404

    components = db.get_component_names(sprint)
    if component not in components:
        return 'I don\'t have results for this component... Sorry... :/', 404
    components.remove(component)

    data = []
    for suite_name in suite_names:

        suite_data = dict()
        suite_data['name'] = suite_name
        tests = [r for r in test_results if r['suite'] == suite_name]
        tests.sort(key=lambda x: x['result'])
        suite_data['rows'] = tests
        suite_data['total'] = len(tests)
        suite_data['passed'] = len([t for t in tests if t['result'] == 'passed'])
        suite_data['failed'] = len([t for t in tests if t['result'] != 'passed'])
        suite_data['has_errors'] = any('error' in test for test in tests)
        suite_data['has_comments'] = any('comment' in test for test in tests)
        suite_data['has_attributes'] = any('attributes' in test for test in tests)

        data.append(suite_data)

    data.sort(key=lambda e: e['name'])

    return render_template('results_suites.html',
                           data=data,
                           project=project,
                           projects=projects,
                           sprint=sprint,
                           sprints=sprints,
                           component=component,
                           components=components)


@server.route('/<project>')
def project_sprints(project):

    db = get_db(project)
    projects = db.get_project_names()
    sprints = db.get_sprint_names()

    if project not in projects:
        return 'I don\'t have results for this project... Sorry... :/', 404
    projects.remove(project)

    return render_template('project_sprints.html',
                           project=project,
                           projects=projects,
                           sprints=sprints)

@server.route('/_delete_suite/<project>/<sprint>/<component>/<suite>', methods=['DELETE'])
def delete_suite(project, sprint, component, suite):

    db = get_db(project)
    db.remove_suite(sprint, component, suite)

    return '', 200

@server.route('/_delete_component/<project>/<sprint>/<component>', methods=['DELETE'])
def delete_component(project, sprint, component):

    db = get_db(project)
    db.remove_component(sprint, component)

    return '', 200

@server.route('/_delete_results/<project>/<sprint>', methods=['DELETE'])
def delete_results(project, sprint):

    db = get_db(project)
    db.remove_results(sprint)

    return '', 200

@server.route('/_rename_results/<project>/<results>/<new_results>', methods=['PUT'])
def rename_results(project, results, new_results):

    db = get_db(project)
    db.rename_results(results, new_results)

    return '', 200

@server.route('/_get_sprint_totals/<project>/<sprint>', methods=['GET'])
def get_sprint_totals(project, sprint):

    db = get_db(project)
    test_results = db.get_test_results(sprint)
    totals = dict()
    totals['total'] = len(test_results)
    totals['passed'] = len([t for t in test_results if t['result'] == 'passed'])
    totals['failed'] = len([t for t in test_results if t['result'] != 'passed'])

    return json.dumps(totals), 200

@server.route('/_get_results_names/<project>', methods=['GET'])
def get_results_names(project):

    db = get_db(project)
    results_names = db.get_sprint_names()

    return json.dumps(results_names), 200


if __name__ == '__main__':

    server.run(host='0.0.0.0', port=5000, debug=True)


# EOF
