from torchvision.utils import make_grid
import tqdm
from scipy.stats import levy_stable
import matplotlib.pyplot as plt
from losses import *
import numpy as np
import torch
from Diffusion import *

from levy_stable_pytorch import LevyStable
levy = LevyStable()

if torch.cuda.is_available():
    device = 'cuda'
else:
    device = 'cpu'
## Sample visualization.

if torch.cuda.is_available():
    device = 'cuda'
else:
    device = 'cpu'


## Sample visualization.

def visualization(samples, sample_batch_size=64):
    samples = samples.clamp(0.0, 1.0)
    sample_grid = make_grid(samples, nrow=int(np.sqrt(sample_batch_size)))
    plt.figure(figsize=(6, 6))
    plt.axis('off')
    plt.imshow(sample_grid.permute(1, 2, 0).cpu(), vmin=0., vmax=1.)


def gamma_func(x):
    return torch.tensor(gamma(x))


def get_discrete_time(t, N=1000):
    return N * t


def ddim_score_update(model, sde, x_s, s, t, return_noise=False):
    score_s = model(x_s, get_discrete_time(s))
    sigma_s = sde.marginal_std(s)

    e_L = levy.sample(sde.alpha, 0, x_s.shape).to(device)
    #e_L = levy_stable.rvs(alpha=sde.alpha, beta=0, loc=0, scale=1, size=x_s.shape)
    #e_L = torch.Tensor(e_L).to(device)
    time_step = torch.abs(t - s)

    x_coeff = 1 + sde.beta(s) / sde.alpha
    noise_coeff = torch.pow(sde.beta(t, 1 / sde.alpha))

    if sde.alpha == 2:
        score_coeff = 2 * noise_coeff ** 2

    else:
        score_coeff = 2 * gamma_func(sde.alpha + 1) / torch.pi * np.sin(torch.pi / 2 * (2 - sde.alpha)) * torch.pow(
            noise_coeff, 2) / (2 - sde.alpha) * torch.pow(time_step, 1 - 2 / sde.alpha)

    x_t = x_coeff[:, None, None, None] * x_s + score_coeff[:, None, None, None] * score_s + sigma_s[:, None, None,
                                                                                            None] * e_L

    if return_noise:
        return x_t, score_s
    else:
        return x_t


def ddim_score_update2(model, sde, x_s, s, t, h=0.006):
    step_size = torch.abs(t - s)
    score_s = model(x_s,s)

    x_coeff = 1 + sde.beta(s) / sde.alpha * step_size

    score_coeff = 2 * sde.beta(s) * step_size * gamma_func(sde.alpha - 1) / torch.pow(gamma_func(sde.alpha / 2),
                                                                                      2) / np.power(h, sde.alpha - 2)
    noise_coeff = torch.pow(sde.beta(s) * step_size, 1 / sde.alpha)
    size = x_s.shape
    e_L = levy.sample(sde.alpha, 0, size).to(device)
    #e_L = levy_stable.rvs(alpha=sde.alpha, beta=0, loc=0, scale=1, size=x_s.shape)
    #e_L = torch.Tensor(e_L).to(device)

    #print('score', torch.min(sde.marginal_std(s)[:, None, None, None] * score_s),

    torch.max(sde.marginal_std(s)[:, None, None, None] * score_s)
    #print('==')
    #print('diff', torch.abs(torch.min(sde.marginal_std(s)[:, None, None, None] * score_s + 1 / 2 * e_L)),

    torch.abs(torch.max(sde.marginal_std(s)[:, None, None, None] * score_s + 1 / 2 * e_L))
    #print('mar', torch.min(sde.marginal_std(t)))

    #print('e', torch.min(-1 / 2 * e_L), torch.max(-1 / 2 * e_L))

    x_t = x_coeff[:, None, None, None] * x_s + score_coeff[:, None, None, None] * score_s + noise_coeff[:, None, None,
                                                                                            None] * e_L
    return x_t


def pc_sampler2(score_model,
                sde,
                alpha,
                batch_size,
                num_steps,
                LM_steps=200,
                device=device,
                eps=1e-3,
                Predictor=True,
                Corrector=False):
    t = torch.ones(batch_size, device=device)
    x_s = levy.sample(alpha, 0, (batch_size, 3, 32,32)).to(device)
    a =torch.linspace(1,0.1, x_s.shape[0])
    #e_L = levy_stable.rvs(alpha=alpha, beta=0, loc=0, scale=1, size=(batch_size, 1, 28, 28))
    #x_s= torch.Tensor(e_L).to(device)

    time_steps = torch.linspace(1., eps, num_steps)  # (t_{N-1}, t_{N-2}, .... t_0)
    step_size = time_steps[0] - time_steps[1]

    batch_time_step_s = torch.ones(batch_size) * time_steps[0]
    batch_time_step_s = batch_time_step_s.to(device)

    visualization(x_s)

    alpha = sde.alpha


    with torch.no_grad():
        for t in tqdm.tqdm(time_steps[1:]):
            batch_time_step_t = torch.ones(batch_size)*t
            batch_time_step_t = batch_time_step_t.to(device)

            if Corrector:
                print('??????')
                for j in range(LM_steps):
                    grad = score_model(x_s, batch_time_step_t)
                    e_L = levy.sample(sde.alpha, 0, (batch_size, 3, 32,32)).to(device)
                    #e_L = levy_stable.rvs(alpha=alpha, beta=0, loc=0, scale=1, size=(batch_size, 1, 28, 28))
                    #e_L = torch.Tensor(e_L).to(device)

                    x_s = x_s -step_size * gamma_func(sde.alpha - 1) / (
                            gamma_func(sde.alpha / 2) ** 2) * grad + np.power(step_size, 1 / sde.alpha) * e_L
                    # visualization(x_s)

            # Predictor step (Euler-Maruyama)
            if Predictor:
                x_s = ddim_score_update2(score_model, sde, x_s, batch_time_step_s, batch_time_step_t)
                # visualization(x_s)
            batch_time_step_s = batch_time_step_t


    x_t = x_s
    visualization(x_t, batch_size)
    return x_t


def pc_sampler(score_model,
               sde,
               alpha,
               batch_size,
               num_steps,
               LM_steps=20,
               device=device,
               eps=1e-3,
               Predictor=True,
               Corrector=True):
    t = torch.ones(batch_size, device=device)
    sigma = sde.marginal_std(t)
    e_L = levy.sample(sde.alpha,0, (batch_size, 3, 32,32)).to(device)
    #e_L = levy_stable.rvs(alpha=alpha, beta=0, loc=0, scale=1, size=(batch_size, 1, 28, 28))
    #e_L = torch.Tensor(e_L).to(device)
    init_x = e_L
    time_steps = np.linspace(1., eps, num_steps)  # (t_{N-1}, t_{N-2}, .... t_0)
    step_size = time_steps[0] - time_steps[1]

    x_s = init_x * sigma[:, None, None, None]

    i = 0
    alpha = sde.alpha
    batch_time_step_s = torch.ones(batch_size, device=device) * time_steps[0]

    visualization(x_s)

    with torch.no_grad():
        for time_step in tqdm.tqdm(time_steps[1:]):

            batch_time_step_t = torch.ones(batch_size, device=device) * time_step

            if Corrector:
                for j in range(LM_steps):
                    grad = score_model(x_s, get_discrete_time(batch_time_step_s))
                    e_L=levy.sample(sde.alpha, 0, (batch_size, 3, 32,32)).to(device)
                    #e_L = levy_stable.rvs(alpha=alpha, beta=0, loc=0, scale=1, size=(batch_size, 1, 28, 28))
                    #e_L = torch.Tensor(e_L).to(device)

                    x_s = x_s + step_size * gamma_func(sde.alpha - 1) / (
                            gamma_func(sde.alpha / 2) ** 2) * grad + np.power(step_size, 1 / sde.alpha) * e_L
                    visualization(x_s)

            # Predictor step (Euler-Maruyama)
            if Predictor:
                x_s = ddim_score_update(score_model, sde, x_s, batch_time_step_s, batch_time_step_t)

            batch_time_step_s = batch_time_step_t

            visualization(x_s)

    x_t = x_s

    return x_t


def dpm_score_update(model, sde, x_s, s, t, alpha, h=0.06, return_noise=False):
    log_alpha_s, log_alpha_t = sde.marginal_log_mean_coeff(s), sde.marginal_log_mean_coeff(t)
    lambda_s = sde.marginal_lambda(s)
    lambda_t = sde.marginal_lambda(t)
    sigma_s = sde.marginal_std(s)
    sigma_t = sde.marginal_std(t)

    score_s = model(x_s, get_discrete_time(s))

    h_t = lambda_t - lambda_s

    x_coeff = torch.exp(log_alpha_t - log_alpha_s)

    score_coeff = sigma_t * torch.pow(sigma_s, alpha - 1) * alpha * torch.expm1(h_t) \
                  * gamma_func(alpha - 1) / torch.pow(gamma_func(alpha / 2), 2) / np.power(h, alpha - 2)

    x_t = x_coeff[:, None, None, None] * x_s + score_coeff[:, None, None, None] * score_s

    return x_t


def dpm_sampler(score_model,
                sde,
                alpha,
                batch_size,
                num_steps,
                device=device,
                eps=1e-3):
    e_L=levy.sample(sde.alpha, 0, (batch_size, 3, 32,32)).to(device)
    #e_L = levy_stable.rvs(alpha=alpha, beta=0, loc=0, scale=1, size=(batch_size, 1, 28, 28))
    #e_L = torch.Tensor(e_L).to(device)


    time_steps = np.linspace(1., eps, num_steps)  # (t_{N-1}, t_{N-2}, .... t_0)
    x_s = e_L

    visualization(x_s)
    i = 0

    alpha = sde.alpha

    batch_time_step_s = torch.ones(batch_size, device=device) * time_steps[0]

    with torch.no_grad():
        for time_step in tqdm.tqdm(time_steps[1:]):
            batch_time_step_t = torch.ones(batch_size, device=device) * time_step

            x_t = dpm_score_update(score_model, sde, x_s, batch_time_step_s, batch_time_step_t, alpha)

            batch_time_step_s = batch_time_step_t

            # visualization(x_s)
        # The last step does not include any noise
        return x_t

