import torch
import torch.nn as nn
import numpy as np
import torch.nn.functional as F

# sv407 - enforces smoothness and continuity in predicted functions (by penalizing changes in adjacent pixel values -> computes the gradient of the image)
class gradientLoss(nn.Module):
    def __init__(self, penalty='l1'):
        super(gradientLoss, self).__init__()
        self.penalty = penalty

    def forward(self, input):
        dD = torch.abs(input[:, :, 1:, :, :] - input[:, :, :-1, :, :])
        dH = torch.abs(input[:, :, :, 1:, :] - input[:, :, :, :-1, :])
        dW = torch.abs(input[:, :, :, :, 1:] - input[:, :, :, :, :-1])
        if(self.penalty == "l2"):
            dD = dD * dD
            dH = dH * dH
            dW = dW * dW
        loss = (torch.mean(dD) + torch.mean(dH) + torch.mean(dW)) / 3.0
        return loss
    
# sv407 - this is a custom CC function written initially for TransMorph paper https://github.com/junyuchen245/TransMorph_Transformer_for_Medical_Image_Registration
# cross correlation is built by emphasizing similarity between local neighbourhoods of exctracted patches (through convolution operation)
class crossCorrelation3D(nn.Module):
    def __init__(self, in_ch, kernel=(9, 9, 9), voxel_weights=None):
        super(crossCorrelation3D, self).__init__()
        self.in_ch = in_ch
        self.kernel = kernel
        self.voxel_weight = voxel_weights
        self.filt = (torch.ones([1, in_ch, self.kernel[0], self.kernel[1], self.kernel[2]])).cuda()


    def forward(self, input, target):
        min_max = (-1, 1)
        target = (target - min_max[0]) / (min_max[1] - min_max[0])  # to range [0,1]

        II = input * input
        TT = target * target
        IT = input * target

        pad = (int((self.kernel[0]-1)/2), int((self.kernel[1]-1)/2), int((self.kernel[2]-1)/2))
        T_sum = F.conv3d(target, self.filt, stride=1, padding=pad)
        I_sum = F.conv3d(input, self.filt, stride=1, padding=pad)
        TT_sum = F.conv3d(TT, self.filt, stride=1, padding=pad)
        II_sum = F.conv3d(II, self.filt, stride=1, padding=pad)
        IT_sum = F.conv3d(IT, self.filt, stride=1, padding=pad)
        kernelSize = self.kernel[0] * self.kernel[1] * self.kernel[2]
        Ihat = I_sum / kernelSize
        That = T_sum / kernelSize

        # cross = (I-Ihat)(J-Jhat)
        cross = IT_sum - Ihat*T_sum - That*I_sum + That*Ihat*kernelSize
        T_var = TT_sum - 2*That*T_sum + That*That*kernelSize
        I_var = II_sum - 2*Ihat*I_sum + Ihat*Ihat*kernelSize
        cc = cross*cross / (T_var*I_var+1e-5)

        loss = -1.0 * torch.mean(cc)
        return loss
