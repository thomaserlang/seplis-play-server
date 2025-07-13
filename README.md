Play server config:
```
database: 'mysql+pymysql://user:password@mysql:3306/seplis_play'
secret: <long random secret>
transcode_folder: /play_temp
server_id: <Id from seplis.net>
api_url: https://api.seplis.net
ffmpeg_hwaccel_enabled: true
ffmpeg_hwaccel: qsv
ffmpeg_tonemap_enabled: false
scan:
  -
    type: series
    path: '/data/series'
    make_thumbnails: no
  -
    type: series
    path: '/data/anime'
    make_thumbnails: no
  -
    type: movies
    path: '/data/movies'
    make_thumbnails: no
```

Kubernetes:
```
apiVersion: v1
kind: Service
metadata:
  name: seplis-play-server
spec:
  selector:
    app: seplis-play-server
  ports:
    - name: seplis-play-server
      port: 8000
      targetPort: 8000

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: seplis-play-server
  labels:
    app: seplis-play-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: seplis-play-server
  template:
    metadata:
      labels:
        app: seplis-play-server
    spec:
      terminationGracePeriodSeconds: 65
      securityContext:
        runAsUser: 10000
        runAsGroup: 10001
        supplementalGroups:
          - 44
      containers:
        - name: seplis
          image: seplis/seplis-play-server:latest
          imagePullPolicy: Always
          args: ["run"]
          ports:
            - containerPort: 8000
          securityContext:
            privileged: true
          volumeMounts:
            - name: config
              mountPath: /etc/seplis_play_server.yaml
              subPath: play-server.yml
            - name: data
              mountPath: /data
            - name: play-temp
              mountPath: /play_temp
            - name: "render-device"
              mountPath: "/dev/dri/renderD128"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 3
            periodSeconds: 30
          env:
            - name: SEPLIS_PLAY_DATABASE
              valueFrom:
                secretKeyRef:
                  name: seplis-secrets
                  key: play_database
                  optional: false
            - name: SEPLIS_PLAY_SECRET
              valueFrom:
                secretKeyRef:
                  name: seplis-secrets
                  key: play_secret
                  optional: false
      volumes:
        - name: config
          configMap:
            name: seplis-play-server-config
        - name: data
          hostPath: 
            path: /data
            type: Directory
        - name: play-temp
          hostPath: 
            path: /data/tmp/seplis-temp
            type: Directory
        - name: "render-device"
          hostPath:
            path: "/dev/dri/renderD128"
```
