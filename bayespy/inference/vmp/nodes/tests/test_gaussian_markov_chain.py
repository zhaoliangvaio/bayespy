######################################################################
# Copyright (C) 2013-2014 Jaakko Luttinen
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

"""
Unit tests for gaussian_markov_chain module.
"""

import unittest

import numpy as np

from numpy import testing

from ..gaussian_markov_chain import GaussianMarkovChain
from ..gaussian_markov_chain import DriftingGaussianMarkovChain
from ..gaussian import Gaussian
from ..gaussian import GaussianArrayARD
from ..wishart import Wishart
from ..gamma import Gamma

from bayespy.utils import random
from bayespy.utils import linalg
from bayespy.utils import utils

from bayespy.utils.utils import TestCase

class TestGaussianMarkovChain(unittest.TestCase):

    def create_model(self, N, D):

        # Construct the model
        Mu = Gaussian(np.random.randn(D),
                      np.identity(D))
        Lambda = Wishart(D,
                         random.covariance(D))
        A = Gaussian(np.random.randn(D,D),
                     np.identity(D))
        V = Gamma(D,
                  np.random.rand(D))
        X = GaussianMarkovChain(Mu, Lambda, A, V, n=N)
        Y = Gaussian(X.as_gaussian(), np.identity(D))

        return (Y, X, Mu, Lambda, A, V)
        

    def test_plates(self):
        """
        Test that plates are handled correctly.
        """

    def test_message_to_mu0(self):
        pass

    def test_message_to_Lambda0(self):
        pass

    def test_message_to_A(self):
        pass

    def test_message_to_v(self):
        pass

    def test_message_to_child(self):
        pass

    def test_moments(self):
        """
        Test the updating of GaussianMarkovChain.

        Check that the moments and the lower bound contribution are computed
        correctly.
        """

        # TODO: Add plates and missing values!

        # Dimensionalities
        D = 3
        N = 5
        (Y, X, Mu, Lambda, A, V) = self.create_model(N, D)

        # Inference with arbitrary observations
        y = np.random.randn(N,D)
        Y.observe(y)
        X.update()
        (x_vb, xnxn_vb, xpxn_vb) = X.get_moments()

        # Get parameter moments
        (mu0, mumu0) = Mu.get_moments()
        (icov0, logdet0) = Lambda.get_moments()
        (a, aa) = A.get_moments()
        (icov_x, logdetx) = V.get_moments()
        icov_x = np.diag(icov_x)
        # Prior precision
        Z = np.einsum('...kij,...kk->...ij', aa, icov_x)
        U_diag = [icov0+Z] + (N-2)*[icov_x+Z] + [icov_x]
        U_super = (N-1) * [-np.dot(a.T, icov_x)]
        U = utils.block_banded(U_diag, U_super)
        # Prior mean
        mu_prior = np.zeros(D*N)
        mu_prior[:D] = np.dot(icov0,mu0)
        # Data 
        Cov = np.linalg.inv(U + np.identity(D*N))
        mu = np.dot(Cov, mu_prior + y.flatten())
        # Moments
        xx = mu[:,np.newaxis]*mu[np.newaxis,:] + Cov
        mu = np.reshape(mu, (N,D))
        xx = np.reshape(xx, (N,D,N,D))

        # Check results
        testing.assert_allclose(x_vb, mu,
                                err_msg="Incorrect mean")
        for n in range(N):
            testing.assert_allclose(xnxn_vb[n,:,:], xx[n,:,n,:],
                                    err_msg="Incorrect second moment")
        for n in range(N-1):
            testing.assert_allclose(xpxn_vb[n,:,:], xx[n,:,n+1,:],
                                    err_msg="Incorrect lagged second moment")


        # Compute the entropy H(X)
        ldet = linalg.logdet_cov(Cov)
        H = random.gaussian_entropy(-ldet, N*D)
        # Compute <log p(X|...)>
        xx = np.reshape(xx, (N*D, N*D))
        mu = np.reshape(mu, (N*D,))
        ldet = -logdet0 - np.sum(np.ones((N-1,D))*logdetx)
        P = random.gaussian_logpdf(np.einsum('...ij,...ij', 
                                                   xx, 
                                                   U),
                                         np.einsum('...i,...i', 
                                                   mu, 
                                                   mu_prior),
                                         np.einsum('...ij,...ij', 
                                                   mumu0,
                                                   icov0),
                                         -ldet,
                                         N*D)
                                                   
        # The VB bound from the net
        l = X.lower_bound_contribution()

        testing.assert_allclose(l, H+P)
                                                   

        # Compute the true bound <log p(X|...)> + H(X)
        
        

    def test_smoothing(self):
        """
        Test the posterior estimation of GaussianMarkovChain.

        Create time-variant dynamics and compare the results of BayesPy VB
        inference and standard Kalman filtering & smoothing.

        This is not that useful anymore, because the moments are checked much
        better in another test method.
        """

        #
        # Set up an artificial system
        #

        # Dimensions
        N = 500
        D = 2
        # Dynamics (time varying)
        A0 = np.array([[.9, -.4], [.4, .9]])
        A1 = np.array([[.98, -.1], [.1, .98]])
        l = np.linspace(0, 1, N-1).reshape((-1,1,1))
        A = (1-l)*A0 + l*A1
        # Innovation covariance matrix (time varying)
        v = np.random.rand(D)
        V = np.diag(v)
        # Observation noise covariance matrix
        C = np.identity(D)

        #
        # Simulate data
        #
        
        X = np.empty((N,D))
        Y = np.empty((N,D))

        x = np.array([0.5, -0.5])
        X[0,:] = x
        Y[0,:] = x + np.random.multivariate_normal(np.zeros(D), C)
        for n in range(N-1):
            x = np.dot(A[n,:,:],x) + np.random.multivariate_normal(np.zeros(D), V)
            X[n+1,:] = x
            Y[n+1,:] = x + np.random.multivariate_normal(np.zeros(D), C)

        #
        # BayesPy inference
        #

        # Construct VB model
        Xh = GaussianMarkovChain(np.zeros(D), np.identity(D), A, 1/v, n=N)
        Yh = Gaussian(Xh.as_gaussian(), np.identity(D), plates=(N,))
        # Put data 
        Yh.observe(Y)
        # Run inference
        Xh.update()
        # Store results
        Xh_vb = Xh.u[0]
        CovXh_vb = Xh.u[1] - Xh_vb[...,np.newaxis,:] * Xh_vb[...,:,np.newaxis]

        #
        # "The ground truth" using standard Kalman filter and RTS smoother
        #
        V = N*(V,)
        UY = Y
        U = N*(C,)
        (Xh, CovXh) = utils.kalman_filter(UY, U, A, V, np.zeros(D), np.identity(D))
        (Xh, CovXh) = utils.rts_smoother(Xh, CovXh, A, V)

        #
        # Check results
        #
        self.assertTrue(np.allclose(Xh_vb, Xh))
        self.assertTrue(np.allclose(CovXh_vb, CovXh))
        

class TestDriftingGaussianMarkovChain(TestCase):

    def test_plates_from_parents(self):
        """
        Test that DriftingGaussianMarkovChain deduces plates correctly
        """
        def check(plates_X,
                  plates_mu=(),
                  plates_Lambda=(),
                  plates_B=(),
                  plates_S=(),
                  plates_v=()):
            
            D = 3
            K = 2
            N = 4

            np.random.seed(42)
            mu = Gaussian(np.random.randn(*(plates_mu+(D,))),
                          random.covariance(D))
            Lambda = Wishart(D+np.ones(plates_Lambda),
                             random.covariance(D))
            B = GaussianArrayARD(np.random.randn(*(plates_B+(D,D,K))),
                                 1+np.random.rand(*(plates_B+(D,D,K))),
                                 shape=(D,K),
                                 plates=plates_B+(D,))
            S = GaussianArrayARD(np.random.randn(*(plates_S+(N,K))),
                                 1+np.random.rand(*(plates_S+(N,K))),
                                 shape=(K,),
                                 plates=plates_S+(N,))
            v = Gamma(1+np.random.rand(*(plates_v+(1,D))),
                      1+np.random.rand(*(plates_v+(1,D))))
            X = DriftingGaussianMarkovChain(mu,
                                            Lambda,
                                            B,
                                            S,
                                            v,
                name="X")
            self.assertEqual(plates_X, X.plates,
                             msg="Incorrect plates deduced")
            pass

        check(())
        check((2,3),
              plates_mu=(2,3))
        check((2,3),
              plates_Lambda=(2,3))
        check((2,3),
              plates_B=(2,3))
        check((2,3),
              plates_S=(2,3))
        check((2,3),
              plates_v=(2,3))
        pass

    def test_message_to_child(self):

        # A very simple check before the more complex ones:
        # 1-D process, k=1, fixed constant parameters
        m = 1.0
        l = 4.0
        b = 2.0
        s = [3.0, 8.0]
        v = 5.0
        X = DriftingGaussianMarkovChain([m],
                                        [[l]],
                                        [[[b]]],
                                        [[s[0]],[s[1]]],
                                        [v])
        (u0, u1, u2) = X._message_to_child()
        C = np.array([[l+b**2*s[0]**2*v,        -b*s[0]*v,         0],
                      [       -b*s[0]*v, v+b**2*s[1]**2*v, -b*s[1]*v],
                      [               0,        -b*s[1]*v,         v]])
        Cov = np.linalg.inv(C)
        m0 = np.dot(Cov, [[l*m], [0], [0]])
        m1 = np.diag(Cov)[:,None,None] + m0[:,:,None]**2
        m2 = np.diag(Cov, k=1)[:,None,None] + m0[1:,:,None]*m0[:-1,:,None]
        self.assertAllClose(m0, u0)
        self.assertAllClose(m1, u1)
        self.assertAllClose(m2, u2)

        def check(N, D, K, plates=None, mu=None, Lambda=None, B=None, S=None, V=None):
            if mu is None:
                mu = np.random.randn(D)
            if Lambda is None:
                Lambda = random.covariance(D)
            if B is None:
                B = np.random.randn(D,D,K)
            if S is None:
                S = np.random.randn(N-1,K)
            if V is None:
                V = np.random.rand(D)
            X = DriftingGaussianMarkovChain(mu,
                                            Lambda,
                                            B,
                                            S,
                                            V,
                                            plates=plates,
                                            n=N)
            (u0, u1, u2) = X._message_to_child()
            (mu, mumu) = X.parents[0].get_moments()
            (Lambda, _) = X.parents[1].get_moments()
            (b, bb) = X.parents[2].get_moments()
            (s, ss) = X.parents[3].get_moments()
            (v, _) = X.parents[4].get_moments()
            v = v * np.ones((N-1,D))
            #V = np.atleast_3d(v)[...,-1,:,None]*np.identity(D)
            plates_C = X.plates
            plates_mu = X.plates
            C = np.zeros(plates_C + (N,D,N,D))
            plates_mu = np.shape(mu)[:-1]
            m = np.zeros(plates_mu + (N,D))
            m[...,0,:] = np.einsum('...ij,...j->...i', Lambda, mu)
            #m = np.reshape(m, plates_mu + (N*D,))
            A = np.einsum('...dik,...nk->...ndi', b, s)
            AA = np.einsum('...dikjl,...nkl->...ndij', bb, ss)
            C[...,0,:,0,:] = Lambda + np.einsum('...dij,...d->...ij',
                                                AA[...,0,:,:,:],
                                                v[...,0,:])
            for n in range(1,N-1):
                C[...,n,:,n,:] = (np.einsum('...dij,...d->...ij',
                                            AA[...,n,:,:,:],
                                            v[...,n,:])
                                  + v[...,n,:,None] * np.identity(D))
            for n in range(N-1):
                C[...,n,:,n+1,:] = -np.einsum('...di,...d->...id',
                                              A[...,n,:,:],
                                              v[...,n,:])
                C[...,n+1,:,n,:] = -np.einsum('...di,...d->...di',
                                              A[...,n,:,:],
                                              v[...,n,:])
            C[...,-1,:,-1,:] = v[...,-1,:,None]*np.identity(D)
            C = np.reshape(C, plates_C+(N*D,N*D))
            Cov = np.linalg.inv(C)
            Cov = np.reshape(Cov, plates_C+(N,D,N,D))
            m0 = np.einsum('...minj,...nj->...mi', Cov, m)
            m1 = np.zeros(plates_C+(N,D,D))
            m2 = np.zeros(plates_C+(N-1,D,D))
            for n in range(N):
                m1[...,n,:,:] = Cov[...,n,:,n,:] + np.einsum('...i,...j->...ij',
                                                             m0[...,n,:],
                                                             m0[...,n,:])
            for n in range(N-1):
                m2[...,n,:,:] = Cov[...,n,:,n+1,:] + np.einsum('...i,...j->...ij',
                                                               m0[...,n,:],
                                                               m0[...,n+1,:])
            self.assertAllClose(m0, u0*np.ones(np.shape(m0)))
            self.assertAllClose(m1, u1*np.ones(np.shape(m1)))
            self.assertAllClose(m2, u2*np.ones(np.shape(m2)))

            pass

        check(2,1,1)
        check(2,3,1)
        check(2,1,3)
        check(4,3,2)

        #
        # Test mu
        #

        # Simple
        check(4,3,2,
              mu=Gaussian(np.random.randn(3),
                          random.covariance(3)))
        # Plates
        check(4,3,2,
              mu=Gaussian(np.random.randn(5,6,3),
                          random.covariance(3),
                          plates=(5,6)))
        # Plates with moments broadcasted over plates
        check(4,3,2,
              mu=Gaussian(np.random.randn(3),
                          random.covariance(3),
                          plates=(5,)))
        check(4,3,2,
              mu=Gaussian(np.random.randn(1,3),
                          random.covariance(3),
                          plates=(5,)))
        # Plates broadcasting
        check(4,3,2,
              plates=(5,),
              mu=Gaussian(np.random.randn(3),
                          random.covariance(3),
                          plates=()))
        check(4,3,2,
              plates=(5,),
              mu=Gaussian(np.random.randn(1,3),
                          random.covariance(3),
                          plates=(1,)))

        #
        # Test Lambda
        #
            
        # Simple
        check(4,3,2,
              Lambda=Wishart(10+np.random.rand(),
                             random.covariance(3)))
        # Plates
        check(4,3,2,
              Lambda=Wishart(10+np.random.rand(),
                             random.covariance(3),
                             plates=(5,6)))
        # Plates with moments broadcasted over plates
        check(4,3,2,
              Lambda=Wishart(10+np.random.rand(),
                             random.covariance(3),
                             plates=(5,)))
        check(4,3,2,
              Lambda=Wishart(10+np.random.rand(1),
                             random.covariance(3),
                             plates=(5,)))
        # Plates broadcasting
        check(4,3,2,
              plates=(5,),
              Lambda=Wishart(10+np.random.rand(),
                             random.covariance(3),
                             plates=()))
        check(4,3,2,
              plates=(5,),
              Lambda=Wishart(10+np.random.rand(),
                             random.covariance(3),
                             plates=(1,)))

        #
        # Test B
        #

        # Simple
        check(4,3,2,
              B=GaussianArrayARD(np.random.randn(3,3,2),
                                 np.random.rand(3,3,2),
                                 shape=(3,2),
                                 plates=(3,)))
        # Plates
        check(4,3,2,
              B=GaussianArrayARD(np.random.randn(5,6,3,3,2),
                                 np.random.rand(5,6,3,3,2),
                                 shape=(3,2),
                                 plates=(5,6,3)))
        # Plates with moments broadcasted over plates
        check(4,3,2,
              B=GaussianArrayARD(np.random.randn(3,3,2),
                                 np.random.rand(3,3,2),
                                 shape=(3,2),
                                 plates=(5,3)))
        check(4,3,2,
              B=GaussianArrayARD(np.random.randn(1,3,3,2),
                                 np.random.rand(1,3,3,2),
                                 shape=(3,2),
                                 plates=(5,3)))
        # Plates broadcasting
        check(4,3,2,
              plates=(5,),
              B=GaussianArrayARD(np.random.randn(3,3,2),
                                 np.random.rand(3,3,2),
                                 shape=(3,2),
                                 plates=(3,)))
        check(4,3,2,
              plates=(5,),
              B=GaussianArrayARD(np.random.randn(3,3,2),
                                 np.random.rand(3,3,2),
                                 shape=(3,2),
                                 plates=(1,3)))

        #
        # Test S
        #
            
        # Simple
        check(4,3,2,
              S=GaussianArrayARD(np.random.randn(4-1,2),
                                 np.random.rand(4-1,2),
                                 shape=(2,),
                                 plates=(4-1,)))
        # Plates
        check(4,3,2,
              S=GaussianArrayARD(np.random.randn(5,6,4-1,2),
                                 np.random.rand(5,6,4-1,2),
                                 shape=(2,),
                                 plates=(5,6,4-1,)))
        # Plates with moments broadcasted over plates
        check(4,3,2,
              S=GaussianArrayARD(np.random.randn(4-1,2),
                                 np.random.rand(4-1,2),
                                 shape=(2,),
                                 plates=(5,4-1,)))
        check(4,3,2,
              S=GaussianArrayARD(np.random.randn(1,4-1,2),
                                 np.random.rand(1,4-1,2),
                                 shape=(2,),
                                 plates=(5,4-1,)))
        # Plates broadcasting
        check(4,3,2,
              plates=(5,),
              S=GaussianArrayARD(np.random.randn(4-1,2),
                                 np.random.rand(4-1,2),
                                 shape=(2,),
                                 plates=(4-1,)))
        check(4,3,2,
              plates=(5,),
              S=GaussianArrayARD(np.random.randn(4-1,2),
                                 np.random.rand(4-1,2),
                                 shape=(2,),
                                 plates=(1,4-1,)))

        #
        # Test v
        #
        
        # Simple
        check(4,3,2,
              V=Gamma(np.random.rand(1,3),
                      np.random.rand(1,3),
                      plates=(1,3)))
        check(4,3,2,
              V=Gamma(np.random.rand(3),
                      np.random.rand(3),
                      plates=(3,)))
        # Plates
        check(4,3,2,
              V=Gamma(np.random.rand(5,6,1,3),
                      np.random.rand(5,6,1,3),
                      plates=(5,6,1,3)))
        # Plates with moments broadcasted over plates
        check(4,3,2,
              V=Gamma(np.random.rand(1,3),
                      np.random.rand(1,3),
                      plates=(5,1,3)))
        check(4,3,2,
              V=Gamma(np.random.rand(1,1,3),
                      np.random.rand(1,1,3),
                      plates=(5,1,3)))
        # Plates broadcasting
        check(4,3,2,
              plates=(5,),
              V=Gamma(np.random.rand(1,3),
                      np.random.rand(1,3),
                      plates=(1,3)))
        check(4,3,2,
              plates=(5,),
              V=Gamma(np.random.rand(1,1,3),
                      np.random.rand(1,1,3),
                      plates=(1,1,3)))

        #
        # Uncertainty in both B and S
        #
        check(4,3,2,
              B=GaussianArrayARD(np.random.randn(3,3,2),
                                 np.random.rand(3,3,2),
                                 shape=(3,2),
                                 plates=(3,)),
              S=GaussianArrayARD(np.random.randn(4-1,2),
                                 np.random.rand(4-1,2),
                                 shape=(2,),
                                 plates=(4-1,)))
                            
        pass

    def test_message_to_mu(self):
        # TODO
        pass

    def test_message_to_Lambda(self):
        # TODO
        pass

    def test_message_to_B(self):
        # TODO
        pass

    def test_message_to_S(self):
        # TODO
        pass

    def test_message_to_v(self):
        # TODO
        pass


