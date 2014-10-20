__author__ = 'vyakoviv'


import time

from pymongo import MongoClient


class MyMongoClient(object):

    def __init__(self, hostname, port):

        self._client = MongoClient(hostname, port)

        self._project_db_name = 'project_%s'
        self._cn_last_update = 'last_update'

    def get_project_db(self, project):

        name = self._project_db_name % project
        return self._client[name]

    def get_project_names(self):

        project_names = [dn.split('_', 1)[1] for dn in self._client.database_names() \
                                             if dn.startswith('project_')]
        project_names.sort()
        return project_names

    def get_latest_sprint_name(self, project):

        project_db = self.get_project_db(project)
        last_updates = list(project_db[self._cn_last_update].find())
        if last_updates:
            last_updates.sort(key=lambda r: r['timestamp'])
            return last_updates[-1]['sprint_name']


class AggregationDB(MyMongoClient):

    def __init__(self, hostname, port, project):

        super(AggregationDB, self).__init__(hostname, port)

        self._db = self.get_project_db(project)

        self._cn_tests = 'tests'
        self._cn_results = 'results_%s'

    def upsert_test(self, component, suite, test_id, **test_attributes):

        self._db[self._cn_tests].update(
            {'test_id': test_id, 'suite': suite, 'component': component},
            {'$set': test_attributes}, upsert=True)

    def upsert_test_result(self, sprint, component, suite, test_id, **result_attributes):

        sprint_collection_name = self._cn_results % sprint
        query = {'test_id': test_id, 'suite': suite, 'component': component}
        self._db[sprint_collection_name].remove(query)
        self._db[sprint_collection_name].update(query,
            {'$set': result_attributes}, upsert=True)

        # Update "last_update".
        self._db[self._cn_last_update].update({'sprint_name': sprint},
                                              {'$set': {'timestamp': time.time()}}, upsert=True)

    def get_test_results(self, sprint, **query):

        sprint_collection_name = self._cn_results % sprint
        return list(self._db[sprint_collection_name].find(query))

    def get_sprint_names(self):

        return [cn.split('_', 1)[1] for cn in self._db.collection_names() if cn.startswith('results_')]

    def get_component_names(self, sprint):

        sprint_collection_name = self._cn_results % sprint
        return self._db[sprint_collection_name].distinct('component')

    def remove_suite(self, sprint, component, suite):

        sprint_collection_name = self._cn_results % sprint
        self._db[sprint_collection_name].remove({'component': component, 'suite': suite})

    def remove_component(self, sprint, component):

        sprint_collection_name = self._cn_results % sprint
        self._db[sprint_collection_name].remove({'component': component})

    def remove_results(self, name):

        results_collection_name = self._cn_results % name
        self._db.drop_collection(results_collection_name)

        self._db[self._cn_last_update].remove({'sprint_name': name})

    def rename_results(self, name, new_name):

        results_collection_name = self._cn_results % name
        new_results_collection_name = self._cn_results % new_name
        self._db[results_collection_name].rename(new_results_collection_name)

        self._db[self._cn_last_update].update({'sprint_name': name},
                                              {'$set': {'sprint_name': new_name}},
                                              upsert=False)


if __name__ == '__main__':

    project = 'proj'
    sprint = 'v.1'
    db = AggregationDB(hostname='localhost', port=27017, project=project)

    # import pdb; pdb.set_trace()
    print db.get_sprint_names()

    print db.get_test_results(sprint)

    component = 'Abc'
    suite = 'AddMessage'

    error = \
"""
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
Exception: a
"""

    for num in xrange(17, 20):

        db.upsert_test_result(attributes=[('is_test_for', 'FOOBAR-1'), ('type', 'Functional')],
                              comment='foo-1,23',
                              sprint=sprint,
                              component=component,
                              suite=suite,
                              test_id='BAM-%s' % num,
                              title='Test %s if there is foo bar no more foo bbar no more...' % num,
                              description='Description more...\nfdfdfdf\n gfggfg',
                              result='failed')

    # import pdb; pdb.set_trace()

    print db.get_test_results(sprint)

# EOF
