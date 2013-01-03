# Copyright (C) 2012 Johnny Vestergaard <jkv@unixcluster.dk>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from pymongo import MongoClient
from datetime import datetime
import logging
from bson.errors import InvalidStringData
import string


class MnemoDB(object):
    def __init__(self, database_name):
        conn = MongoClient()
        self.db = conn[database_name]

    def insert_normalized(self, ndata, original_hpfeed):
        for item in ndata:
            #every root item is equal to collection name
            for collection, document in item.items():
                    if collection is 'url':
                        push_dict = {'hpfeed_ids': original_hpfeed['_id']}
                        if 'extractions' in document:
                            push_dict['extractions'] = document['extractions']
                        self.db[collection].update({'url': document['url']}, {'$push': push_dict}, upsert=True)
                    elif collection is 'file':
                        self.db[collection].update({'hashes.sha512': document['hashes']['sha512']}, {'$set': document, '$push': {'hpfeed_ids': original_hpfeed['_id']}}, upsert=True)
                    elif collection is 'session':
                        document['hpfeed_id'] = original_hpfeed['_id']
                        self.db[collection].insert(document)
                    else:
                        raise Warning('{0} is not a know collection type.'.format(collection))
        self.db.hpfeed.update({'_id': original_hpfeed['_id']}, {"$set": {'normalized': True}})

    def insert_hpfeed(self, ident, channel, payload):

        #thanks rep!
        #mongo can't handle non-utf-8 strings, therefore we must encode
        #raw binaries
        if [i for i in payload[:20] if i not in string.printable]:
            payload = str(payload).encode('hex')
        else:
            payload = str(payload)

        entry = {'channel': channel,
                 'ident': ident,
                 'payload': payload,
                 'timestamp': datetime.utcnow(),
                 'normalized': False}
        try:
            self.db.hpfeed.insert(entry)
        except InvalidStringData as err:
            logging.error('Failed to insert hpfeed data on {0} channel due to invalid string data. ({1})'.format(entry['channel'], err))

    def get_hpfeed_data(self, max=None):
        data = self.db.hpfeed.find({'normalized': False})
        return data

    def reset_normalized(self):
        """
        Deletes all normalized data from the mongo instance.
        """
        for collection in self.db.collection_names():
            if collection not in ['system.indexes', 'hpfeed', 'hpfeeds']:
                logging.warning('Dropping collection: {0}.'.format(collection))
                self.db.drop_collection(collection)
        self.db.hpfeed.update({}, {"$set": {'normalized': False}}, multi=True)
        logging.info('Database reset.')

    def collection_count(self):
        result = {}
        for collection in self.db.collection_names():
            if collection not in ['system.indexes']:
                count = self.db[collection].count()
                result[collection] = count
        return result