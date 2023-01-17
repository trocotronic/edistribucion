"""
Created on Tue Jan 17 11:51:36 2022

@author: trocotronic
"""

'''
This example shows how to manage multiple identities and authorizations. It allows, for instance, to get info from other points without requiring credentials.
Note: your user must be authorized by the owner of supply.
'''

from EdistribucionAPI import Edistribucion

edis = Edistribucion()
identities = edis.get_identities()
## We use the first identity
vis = identities[0]['value']
cups_list = edis.get_list_cups(vis=vis)
print(cups_list)
cups = edis.get_cups(vis=vis)
print(cups)
cups = edis.get_all_cups(vis=vis)
print(cups)
## We use the latest CUPS from the selected identity vis
cups_detail = edis.get_cups_detail(cups=cups_list[-1]['CUPS_Id'], vis=vis)
print(cups_detail)
cups_info = edis.get_cups_info(cups=cups_list[-1]['CUPS_Id'], vis=vis)
print(cups_info)
