import gym
from gym.utils import seeding
from gym.spaces import Discrete
import numpy as np
import psutil
import subprocess
import bisect
import time
import os
import multiprocessing

class Kvazaar_v0 (gym.Env):

    REWARD_END = 0

    metadata = {
        "render.modes": ["human"]
    }

    
    def __init__(self, **kwargs):
        # Recogemos los argumentos:
        # kvazaar_path: ruta donde está instalado kvazaar
        # vids_path: ruta de los vídeos que utilizará el entorno
        # cores: lista de cores para kvazaar
        self.kvazaar_path = kwargs.get("kvazaar_path")
        self.vids_path = kwargs.get("vids_path")
        self.cores = kwargs.get("cores") #Lista de los cores que utiliza el entorno
        
        self.action_space = Discrete(len(self.cores))
        self.observation_space = Discrete(11)
        self.kvazaar = None

    
    def reset(self):
        self.seed() #generamos semilla de randoms
        self.directorio = os.listdir(self.vids_path) 
        self.reset_kvazaar()
        self.count = 0
        self.state = np.int64(1)
        self.reward = 0 #la recompensa inicial es 0
        self.done = False
        self.info = {"estado": "running", "fps": 0}
        return self.state

    def reset_kvazaar(self):
        randomInt = self.np_random.randint(0, len(self.directorio))
        new_video = str(self.vids_path + self.directorio[randomInt])
        print("New video selected: " + new_video)

        comando = [self.kvazaar_path, 
                   "--input", new_video, 
                   "--output", "/dev/null", 
                   "--preset=ultrafast", 
                   "--qp=22", "--owf=0", 
                   "--threads=" + str(len(self.cores))]
        
        #aplicamos taskset usando la segunda mitad de cores para kvazaar
        comando = ["taskset","-c",",".join([str(x) for x in self.cores])] + comando
        
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
                1: 0, ##[0,10)
                2: 1, ##[10,16)
                3: 2, ##[16,24)
                4: 3, ##[20,24)
                5: 6, ##[24,27)
                6: 8, ##[27,30)
                7: 10,  ##[30,35)
                8: 7, # [35,40)
                9: 4 # [40,inf)
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
            if output_value < 10: self.state = np.int64(1)
            elif output_value < 16: self.state = np.int(2)
            elif output_value < 20: self.state = np.int(3)
            elif output_value < 24: self.state = np.int(4)
            elif output_value < 27: self.state = np.int64(5)
            elif output_value < 30: self.state = np.int64(6)
            elif output_value < 35: self.state = np.int64(7)
            elif output_value < 40: self.state = np.int64(8) 
            else: self.state = np.int64(9)




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
       if(self.kvazaar): self.kvazaar.kill()
