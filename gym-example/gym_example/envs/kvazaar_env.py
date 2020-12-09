import gym
from gym.utils import seeding
from gym.spaces import Dict, Box, Discrete, MultiDiscrete
import numpy as np
import subprocess
import bisect
import time

class Kvazaar_v0 (gym.Env):
    
    MAX_STEPS = 10
    REWARD_POSITIVE = 1
    REWARD_NEGATIVE = 0

    metadata = {
        "render.modes": ["human"]
    }


    def __init__(self, **kwargs):
        self.kvazaar_path = kwargs.get("kvazaar_path")
        self.vid_path = kwargs.get("vid_path")
        self.nCores = kwargs.get("nCores")
        
        self.action_space = Discrete(self.nCores)
        #El espacio de acciones corresponde a los cores, de 0 a nCores-1
        #el espacio de observaciones es un rango de floats de 0 a 200
        self.observation_space = Box(low=np.array([0]), high=np.array([200]), dtype=np.float32)
        self.goal = 0 #no hay objetivo de momento
        self.kvazaar = None

        self.seed() #generamos semilla de randoms
        # self.reset() #generamos la primera observacion
    
    def reset(self):
        self.reset_kvazaar()
        self.count = 0
        self.state = [0]
        self.reward = 0 #la recompensa inicial es 0
        self.done = False
        self.info = {"estado": "running", "intervalo": 0}
        return self.state

    def reset_kvazaar(self):
        comando = [self.kvazaar_path, 
                   "--input", self.vid_path, 
                   "--output", "/dev/null", 
                   "--preset=ultrafast", 
                   "--qp=22", "--owf=0", 
                   "--threads=" + str(self.nCores)]

        # creamos subproceso de kvazaar
        
        self.kvazaar = subprocess.Popen(comando, 
                                        stdin=subprocess.PIPE, 
                                        stdout=subprocess.PIPE, 
                                        universal_newlines=True, bufsize=1, 
                                        env={'NUM_FRAMES_PER_BATCH': '24'})

        while not self.kvazaar:
            time.sleep(1)

    def step(self, action):
        if self.info["estado"] == 'END':
            self.reset_kvazaar()

        assert self.action_space.contains(action)
        action += 1 #ya que el espacio va de 0 a nCores-1
        
        # LLAMADA A KVAZAAR
        s = "nThs:" + str(action)
        self.kvazaar.stdin.write(s + "\n")
        output= self.kvazaar.stdout.readline().strip()
        ########
        
        self.calculate_state(output=output)
    
        self.info["estado"] = output.strip()
        if self.info["estado"] != 'END':
            self.count += 1

        try:
            assert self.observation_space.contains(self.state) #comprabamos que el nuevo estado es válido
        except AssertionError:
            print("INVALID STATE", self.state)

        return [self.state, self.calculate_reward(), self.done, self.info]
    
    def calculate_reward(self):
        if self.info["estado"] == 'END':
            self.reward = self.REWARD_POSITIVE
        else: self.reward = 0 if(self.state[0] < 24) else 1

        return self.reward

    def calculate_state(self, output):
        if(output == "END"):
            self.done = True
            self.info["estado"] = 'END'
        else:
            ## eliminamos la primera parte de la salida ("FPS:") y la guardamos en el nuevo estado
            output_value = np.float32(output[4:])
            self.info["intervalo"] = 0 if (output_value < 24) else 1
            self.state = [output_value]



    def render(self, mode="human"):
        if self.info["estado"] == 'END':
            print (self.info["estado"])
        else:
            l = '{:>7.1f}  box:{:>1}  reward:{:<10}'.format(self.state[0], self.info["intervalo"], self.reward)
            print(l)

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]
        
    def close(self):
       self.kvazaar.kill()
