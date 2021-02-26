import gym
from gym.utils import seeding
from gym.spaces import Dict, Box, Discrete, MultiDiscrete
import numpy as np
import subprocess
import bisect
import time
import os


class Kvazaar_v0 (gym.Env):

    REWARD_END = 0

    metadata = {
        "render.modes": ["human"]
    }

    
    def __init__(self, **kwargs):
        # Recogemos los argumentos:
        # kvazaar_path: ruta donde está instalado kvazaar
        # vid_path: 
        self.kvazaar_path = kwargs.get("kvazaar_path")
        self.vids_path = kwargs.get("vids_path")
        self.nCores = kwargs.get("nCores")
        
        self.action_space = Discrete(self.nCores)
        #El espacio de acciones corresponde a los cores, de 0 a nCores-1
        #el espacio de observaciones es un espacio discreto
        self.observation_space = Discrete(6)
        self.goal = 0 #no hay objetivo de momento
        self.kvazaar = None

    
    def reset(self):
        self.seed() #generamos semilla de randoms
        self.directorio = os.listdir(self.vids_path)
        print(self.vids_path)
        print(self.directorio)
        self.reset_kvazaar()
        self.count = 0
        self.state = np.int64(1)
        self.reward = 0 #la recompensa inicial es 0
        self.done = False
        self.info = {"estado": "running", "fps": 0}
        return self.state

    def reset_kvazaar(self):
        randomInt = np.randomInt(len(self.directorio))
        new_video = str(self.vids_path + self.directorio[randomInt])
        print("New video selected: " + new_video)

        comando = [self.kvazaar_path, 
                   "--input", new_video, 
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
            self.reward = self.REWARD_END
        else: 
            map_rewards = {
                1: 0,
                2: 10,
                3: 0,
                4: 0,
                5: 0,    
            }
            self.reward = map_rewards.get(self.state)

        return self.reward

    def calculate_state(self, output):
        if(output == "END"):
            self.done = True
            self.info["estado"] = 'END'
        else:
            ## eliminamos la primera parte de la salida ("FPS:") y la guardamos en el nuevo estado
            output_value = np.float32(output[4:])
            
            self.info["fps"] = '{:.2f}'.format(output_value)
            if output_value < 20: self.state = np.int64(1)
            elif output_value < 45: self.state = np.int64(2)
            elif output_value < 100: self.state = np.int64(3)
            elif output_value < 150: self.state = np.int64(4)
            else: output_value: self.state = np.int64(5)




    def render(self, mode="human"):
        if self.info["estado"] == 'END':
            print (self.info["estado"])
        else:
            l = '{:>7}  fps:{:>1}  reward:{:<10}'.format(self.state, self.info["fps"], self.reward)
            print(l)

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]
        
    def close(self):
       self.kvazaar.kill()
