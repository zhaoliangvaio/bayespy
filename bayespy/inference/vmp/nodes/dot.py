######################################################################
# Copyright (C) 2011-2013 Jaakko Luttinen
#
# This file is licensed under Version 3.0 of the GNU General Public
# License. See LICENSE for a text of the license.
######################################################################

######################################################################
# This file is part of BayesPy.
#
# BayesPy is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# BayesPy is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BayesPy.  If not, see <http://www.gnu.org/licenses/>.
######################################################################

import numpy as np

from bayespy.utils import utils

from .node import Node
from .deterministic import Deterministic
from .constant import Constant
from .gaussian import Gaussian


class SumMultiply(Deterministic):
    """
    Compute the sum-product of Gaussian nodes similarly to numpy.einsum.
    
    For instance, the equivalent of
    
        np.einsum('abc,bd,ca->da', X, Y, Z)
        
    would be given as
    
        SumMultiply('abc,bd,ca->da', X, Y, Z)
    or
        SumMultiply(X, [0,1,2], Y, [1,3], Z, [2,0], [3,0])
        
    which is similar to the other syntax of numpy.einsum.

    This node operates similarly as numpy.einsum. However, you must use all the
    elements of each node, that is, an operation like np.einsum('ii->i',X) is
    not allowed. Thus, for each node, each axis must be given unique id. The id
    identifies which axes correspond to which axes between the different
    nodes. Also, Ellipsis ('...') is not yet supported for simplicity.

    Each output axis must appear in the input mappings.

    The keys must refer to variable dimension axes only, not plate axes.

    The convenient string notation of numpy.einsum is not yet implemented.

    Examples
    --------

    Sum over the rows:
    'ij->j'
    
    Inner product of three vectors:
    'i,i,i'

    Matrix-vector product:
    'ij,j->i'

    Matrix-matrix product:
    'ik,kj->ij'

    Outer product:
    'i,j->ij'

    Vector-matrix-vector product:
    'i,ij,j'

    Note
    ----

    This operation can be extremely slow if not used wisely. For large and
    complex operations, it is sometimes more efficient to split the operation
    into multiple nodes. For instance, the example above could probably be
    computed faster by

        XZ = SumMultiply(X, [0,1,2], Z, [2,0], [0,1])
        SumMultiply(XZ, [0,1], Y, [1,2], [2,0])

    because the third axis ('c') could be summed out already in the first
    operation. This same effect applies also to numpy.einsum in general.
    """

    def __init__(self, *args, iterator_axis=None, **kwargs):
        """
        SumMultiply(Node1, map1, Node2, map2, ..., NodeN, mapN [, map_out])
        """

        args = list(args)

        if len(args) < 2:
            raise ValueError("Not enough inputs")

        if iterator_axis is not None:
            raise NotImplementedError("Iterator axis not implemented yet")
        if iterator_axis is not None and not isinstance(iterator_axis, int):
            raise ValueError("Iterator axis must be integer")

        # Two different parsing methods, depends on how the arguments are given
        if utils.is_string(args[0]):
            # This is the format:
            # SumMultiply('ik,k,kj->ij', X, Y, Z)
            strings = args[0]
            nodes = args[1:]
            # Remove whitespace
            strings = utils.remove_whitespace(strings)
            # Split on '->' (should contain only one '->' or none)
            strings = strings.split('->')
            if len(strings) > 2:
                raise ValueError('The string contains too many ->')
            strings_in = strings[0]
            if len(strings) == 2:
                string_out = strings[1]
            else:
                string_out = ''
            # Split former part on ',' (the number of parts should be equal to
            # nodes)
            strings_in = strings_in.split(',')
            if len(strings_in) != len(nodes):
                raise ValueError('Number of given input nodes is different '
                                 'from the input keys in the string')
            # Split strings into key lists using single character keys
            keysets = [list(string_in) for string_in in strings_in]
            keys_out = list(string_out)
            
            
        else:
            # This is the format:
            # SumMultiply(X, [0,2], Y, [2], Z, [2,1], [0,1])

            # If given, the output mapping is the last argument
            if len(args) % 2 == 0:
                keys_out = []
            else:
                keys_out = args.pop(-1)

            # Node and axis mapping are given in turns
            nodes = args[::2]
            keysets = args[1::2]
            
        # Find all the keys (store only once each)
        full_keyset = []
        for keyset in keysets:
            full_keyset += keyset
            #full_keyset += list(keyset.keys())
        full_keyset = list(set(full_keyset))

        #
        # Check the validity of each node
        #
        for n in range(len(nodes)):
            # Convert constant arrays to constant nodes
            if utils.is_numeric(nodes[n]):
                # TODO/FIXME: Use GaussianArray and infer the dimensionality
                # from the length of the axis mapping!
                nodes[n] = Constant(Gaussian)(nodes[n])
            # Check that the maps and the size of the variable are consistent
            if len(nodes[n].dims[0]) != len(keysets[n]):
                raise ValueError("Wrong number of keys (%d) for the node "
                                 "number %d with %d dimensions"
                                 % (len(keysets[n]),
                                    n,
                                    len(nodes[n].dims[0])))
            # Check that the keys are unique
            if len(set(keysets[n])) != len(keysets[n]):
                raise ValueError("Axis keys for node number %d are not unique"
                                 % n)
            # Check that the dims are proper Gaussians
            if len(nodes[n].dims) != 2:
                raise ValueError("Node %d is not Gaussian" % n)
            if nodes[n].dims[0] + nodes[n].dims[0] != nodes[n].dims[1]:
                raise ValueError("Node %d is not Gaussian" % n)

        # Check the validity of output keys: each output key must be included in
        # the input keys
        if len(keys_out) != len(set(keys_out)):
            raise ValueError("Output keys are not unique")
        for key in keys_out:
            if key not in full_keyset:
                raise ValueError("Output key %s does not appear in any input"
                                 % key)

        # Check the validity of the nodes with respect to the key mapping.
        # Check that the node dimensions map and broadcast properly, that is,
        # all the nodes using the same key for axes must have equal size for
        # those axes (or size 1).
        broadcasted_size = {}
        for key in full_keyset:
            broadcasted_size[key] = 1
            for (node, keyset) in zip(nodes, keysets):
                try:
                    # Find the axis for the key
                    index = keyset.index(key)
                except ValueError:
                    # OK, this node doesn't use this key for any axis
                    pass
                else:
                    # Length of the axis for that key
                    node_size = node.dims[0][index]
                    if node_size != broadcasted_size[key]:
                        if broadcasted_size[key] == 1:
                            # Apply broadcasting
                            broadcasted_size[key] = node_size
                        elif node_size != 1:
                            # Different sizes and neither has size 1
                            raise ValueError("Axes using key %s do not "
                                             "broadcast properly"
                                             % key)
                                             

        # Compute the shape of the output
        dim0 = [broadcasted_size[key] for key in keys_out]
        dim1 = dim0 + dim0

        # Rename the keys to [0,1,...,N-1] where N is the total number of keys
        self.N_keys = len(full_keyset)
        self.out_keys = [full_keyset.index(key) for key in keys_out]
        self.in_keys = [ [full_keyset.index(key) for key in keyset]
                         for keyset in keysets ]

        super().__init__(*nodes,
                         dims=(tuple(dim0),tuple(dim1)),
                         **kwargs)

            

    def _compute_moments(self, *u_parents):


        # Compute the number of plate axes for each node
        plate_counts0 = [(np.ndim(u_parent[0]) - len(keys))
                         for (keys,u_parent) in zip(self.in_keys, u_parents)]
        plate_counts1 = [(np.ndim(u_parent[1]) - 2*len(keys))
                         for (keys,u_parent) in zip(self.in_keys, u_parents)]
        # The number of plate axes for the output
        N0 = max(plate_counts0)
        N1 = max(plate_counts1)
        # The total number of unique keys used (keys are 0,1,...,N_keys-1)
        D = self.N_keys

        #
        # Compute the mean
        #
        out_all_keys = list(range(D+N0-1, D-1, -1)) + self.out_keys
        #nodes_dim_keys = self.nodes_dim_keys
        in_all_keys = [list(range(D+plate_count-1, D-1, -1)) + keys
                      for (plate_count, keys) in zip(plate_counts0, 
                                                     self.in_keys)]
        u0 = [u[0] for u in u_parents]
        
        args = utils.zipper_merge(u0, in_all_keys) + [out_all_keys]
        x0 = np.einsum(*args)

        #
        # Compute the covariance
        #
        out_all_keys = (list(range(2*D+N1-1, 2*D-1, -1)) 
                        + [D+key for key in self.out_keys] 
                        + self.out_keys)
        in_all_keys = [list(range(2*D+plate_count-1, 2*D-1, -1)) 
                       + [D+key for key in node_keys]
                       + node_keys
                       for (plate_count, node_keys) in zip(plate_counts1, 
                                                           self.in_keys)]
        u1 = [u[1] for u in u_parents]
        args = utils.zipper_merge(u1, in_all_keys) + [out_all_keys]
        x1 = np.einsum(*args)

        return [x0, x1]


    def get_parameters(self):
        # Compute mean and variance
        u = self.get_moments()
        u[1] -= u[0]**2
        return u
        

    def _message_to_parent(self, index):
        """
        Compute the message and mask to a parent node.
        """

        # Check index
        if index >= len(self.parents):
            raise ValueError("Parent index larger than the number of parents")

        # Get messages from other parents and children
        u_parents = self._message_from_parents(exclude=index)
        m = self._message_from_children()
        mask = self.mask

        # Normally we don't need to care about masks when computing the
        # message. However, in this node we want to avoid computing huge message
        # arrays so we sum some axes already here. Thus, we need to apply the
        # mask.

        parent = self.parents[index]

        #
        # Compute the first message
        #

        msg = [None, None]
        
        # Compute the two messages
        for ind in range(2):

            # The total number of keys for the non-plate dimensions
            N = (ind+1) * self.N_keys

            # Add an array of ones to ensure proper shape and number of
            # plates. Note that this adds an axis for each plate. At the end, we
            # want to remove axes that were created only because of this
            parent_num_dims = len(parent.dims[ind])
            parent_num_plates = len(parent.plates)
            parent_plate_keys = list(range(N + parent_num_plates,
                                           N,
                                           -1))
            parent_dim_keys = self.in_keys[index]
            if ind == 1:
                parent_dim_keys = ([key + self.N_keys
                                    for key in self.in_keys[index]]
                                   + parent_dim_keys)
            args = []
            args.append(np.ones((1,)*parent_num_plates + parent.dims[ind]))
            args.append(parent_plate_keys + parent_dim_keys)

            # This variable counts the maximum number of plates of the
            # arguments, thus it will tell the number of plates in the result
            # (if the artificially added plates above were ignored).
            result_num_plates = 0
            result_plates = ()

            # Mask and its keysr
            mask_num_plates = np.ndim(mask)
            mask_plates = np.shape(mask)
            mask_plate_keys = list(range(N + mask_num_plates, 
                                         N,
                                         -1))
            result_num_plates = max(result_num_plates,
                                    mask_num_plates)
            result_plates = utils.broadcasted_shape(result_plates,
                                                    mask_plates)
            args.append(mask)
            args.append(mask_plate_keys)

            # Moments and keys of other parents
            for (k, u) in enumerate(u_parents):
                if k != index:
                    num_dims = (ind+1) * len(self.in_keys[k])
                    num_plates = np.ndim(u[ind]) - num_dims
                    plates = np.shape(u[ind])[:num_plates]
                    plate_keys = list(range(N + num_plates, 
                                            N,
                                            -1))
                    dim_keys = self.in_keys[k]
                    if ind == 1:
                        dim_keys = ([key + self.N_keys 
                                     for key in self.in_keys[k]]
                                    + dim_keys)
                    args.append(u[ind])
                    args.append(plate_keys + dim_keys)

                    result_num_plates = max(result_num_plates, num_plates)
                    result_plates = utils.broadcasted_shape(result_plates,
                                                            plates)

            # Message and keys from children
            child_num_dims = (ind+1) * len(self.out_keys)
            child_num_plates = np.ndim(m[ind]) - child_num_dims
            child_plates = np.shape(m[ind])[:child_num_plates]
            child_plate_keys = list(range(N + child_num_plates,
                                          N,
                                          -1))
            child_dim_keys = self.out_keys
            if ind == 1:
                child_dim_keys = ([key + self.N_keys
                                   for key in self.out_keys]
                                  + child_dim_keys)
            args.append(m[ind])
            args.append(child_plate_keys + child_dim_keys)

            result_num_plates = max(result_num_plates, child_num_plates)
            result_plates = utils.broadcasted_shape(result_plates,
                                                    child_plates)

            # Output keys, that is, the keys of the parent[index]
            parent_keys = parent_plate_keys + parent_dim_keys

            # Performance trick: Check which axes can be summed because they
            # have length 1 or are non-existing in parent[index]. Thus, remove
            # keys corresponding to unit length axes in parent[index] so that
            # einsum sums over those axes. After computations, these axes must
            # be added back in order to get the correct shape for the message.

            parent_shape = parent.get_shape(ind)
            removed_axes = []
            for j in range(len(parent_keys)):
                if parent_shape[j] == 1:
                    # Remove the key (take into account the number of keys that
                    # have already been removed)
                    del parent_keys[j-len(removed_axes)]
                    removed_axes.append(j)

            args.append(parent_keys)

            # THE BEEF: Compute the message
            msg[ind] = np.einsum(*args)

            # Find the correct shape for the message array
            message_shape = list(np.shape(msg[ind]))
            # First, add back the axes with length 1
            for ax in removed_axes:
                message_shape.insert(ax, 1)
            # Second, remove leading axes for plates that were not present in
            # the child nor other parents' messages. This is not really
            # necessary, but it is just elegant to remove the leading unit
            # length axes that we added artificially at the beginning just
            # because we wanted the key mapping to be simple.
            if parent_num_plates > result_num_plates:
                del message_shape[:(parent_num_plates-result_num_plates)]
            # Then, the actual reshaping
            msg[ind] = np.reshape(msg[ind], message_shape)

            # Apply plate multiplier: If this node has non-unit plates that are
            # unit plates in the parent, those plates are summed. However, if
            # the message has unit axis for that plate, it should be first
            # broadcasted to the plates of this node and then summed to the
            # plates of the parent. In order to avoid this broadcasting and
            # summing, it is more efficient to just multiply by the correct
            # factor.
            r = self._plate_multiplier(self.plates, 
                                       result_plates,
                                       parent.plates)
            if r != 1:
                msg[ind] *= r
        
        return msg

def Dot(*args, **kwargs):
    """
    Node for computing inner product of several Gaussian vectors.

    This is a simple wrapper of the much more general SumMultiply. For now, it
    is here for backward compatibility.
    """
    einsum = 'i' + ',i'*(len(args)-1)
    return SumMultiply(einsum, *args, **kwargs)
